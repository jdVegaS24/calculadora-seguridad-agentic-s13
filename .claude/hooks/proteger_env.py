"""Política local: analiza el evento por stdin; nunca ejecuta tool_input.

No lee archivos, no usa red ni inicia procesos. Siempre termina con código 0:
stdout vacío permite; JSON con permissionDecision="deny" deniega.
El registro y la compatibilidad con Codex se documentan por separado.
"""

import json
import re
import sys


ENV = re.compile(r"(?<![\w.-])\.env\.*(?=$|[\\/\s\"'`;,):\]}|&<>])", re.IGNORECASE)
SIMULADOR = re.compile(r"(?<![\w.-])verificar_entorno\.py(?![\w.-])", re.IGNORECASE)
INTERPRETE = re.compile(
    r"(?<![\w.-])(?:python(?:w|\d+(?:\.\d+)*)?|py)(?:\.exe)?(?![\w.-])",
    re.IGNORECASE,
)
RUTAS = {
    "path", "paths", "file", "files", "file_path", "filepath", "filename",
    "target_file", "file_paths", "relative_path", "source", "destination",
    "destination_path", "source_path", "target", "src", "dest", "new_path", "old_path",
    "cwd", "workdir", "directory", "uri",
}
COMANDOS = {"command", "cmd", "code", "script", "args", "argv", "arguments", "chars"}
SONDA = "--prueba-bloqueo-inerte"
CABECERA_PARCHE = re.compile(
    r"^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$", re.MULTILINE
)


def cadenas(valor):
    if isinstance(valor, str):
        yield valor
    elif isinstance(valor, dict):
        for contenido in valor.values():
            yield from cadenas(contenido)
    elif isinstance(valor, list):
        for contenido in valor:
            yield from cadenas(contenido)


def ejecucion_simulador(comando):
    """Reconoce invocaciones literales; no interpreta Python, JS ni el shell."""
    if re.search(r"(?<!\S)-m\s+verificar_entorno\b", comando, re.IGNORECASE):
        return True
    if not SIMULADOR.search(comando):
        return False
    if INTERPRETE.search(comando):
        return True
    if re.search(r"\b(?:Start-Process|Invoke-Item|Invoke-Expression|saps|iex|ii|start)\b", comando, re.IGNORECASE):
        return True
    for segmento in re.split(r"[;\n|]|&&", comando):
        segmento = segmento.strip().lstrip("& ")
        segmento = re.sub(r"^cmd(?:\.exe)?\s+/[ck]\s+", "", segmento, flags=re.IGNORECASE)
        primero = re.match(r'''(?:"([^"]+)"|'([^']+)'|(\S+))''', segmento)
        if primero:
            ejecutable = next(grupo for grupo in primero.groups() if grupo is not None)
            if ejecutable.replace("\\", "/").rsplit("/", 1)[-1].lower() == "verificar_entorno.py":
                return True
    return False


def revisar_comando(comando):
    if SONDA in comando:
        return "Sonda inerte denegada: el hook sí recibió la solicitud de herramienta."
    if ENV.search(comando):
        return "Acceso directo a .env denegado por la política del laboratorio."
    if ejecucion_simulador(comando):
        return "Ejecución directa de verificar_entorno.py denegada por la política del laboratorio."
    return None


def revisar_parche(parche):
    for ruta in CABECERA_PARCHE.findall(parche):
        if ENV.search(ruta):
            return "Parche sobre .env denegado por la política del laboratorio."
    return None


def revisar_campos(valor):
    if isinstance(valor, dict):
        for nombre, contenido in valor.items():
            clave = nombre.lower()
            textos = list(cadenas(contenido))
            if clave in RUTAS and any(ENV.search(texto) for texto in textos):
                return "Operación directa sobre .env denegada por la política del laboratorio."
            if clave in COMANDOS:
                motivo = revisar_comando(" ".join(textos))
                if motivo:
                    return motivo
            if clave in {"input", "patch"}:
                for texto in textos:
                    motivo = revisar_parche(texto)
                    if motivo:
                        return motivo
            motivo = revisar_campos(contenido)
            if motivo:
                return motivo
    elif isinstance(valor, list):
        for contenido in valor:
            motivo = revisar_campos(contenido)
            if motivo:
                return motivo
    return None


def evaluar(evento):
    if not isinstance(evento, dict):
        return "Evento inválido: se esperaba un objeto JSON."
    if evento.get("hook_event_name") != "PreToolUse":
        return "Evento inválido: este control solo admite PreToolUse."
    if not isinstance(evento.get("tool_name"), str):
        return "Evento inválido: falta tool_name."
    datos = evento.get("tool_input")
    if isinstance(datos, str):
        # Codex puede transportar los argumentos de una herramienta como JSON.
        try:
            datos = json.loads(datos)
        except json.JSONDecodeError:
            if "apply_patch" in evento["tool_name"].lower():
                return revisar_parche(datos)
            return revisar_comando(datos)
    if not isinstance(datos, dict):
        return "Evento inválido: tool_input debe ser un objeto o texto."
    return revisar_campos(datos)


def main():
    for flujo in (sys.stdin, sys.stdout, sys.stderr):
        flujo.reconfigure(encoding="utf-8")
    if sys.argv[1:] == [SONDA]:
        # Si se llega aquí, el hook exterior no impidió esta orden inocua.
        print("SONDA EJECUTADA: esta llamada no fue bloqueada antes de ejecutarse.")
        return 0
    try:
        motivo = evaluar(json.load(sys.stdin))
    except (ValueError, TypeError, RecursionError):
        motivo = "Evento inválido: no se pudo validar; operación denegada."
    if motivo:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": motivo,
            },
        }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
