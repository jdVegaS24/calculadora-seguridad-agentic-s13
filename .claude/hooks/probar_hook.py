"""Banco de pruebas del guardrail, SIN agente ni ejecutar las órdenes de ejemplo.

Uso:  python .claude/hooks/probar_hook.py [ruta_del_hook]     (por defecto .claude/hooks/proteger_env.py)

Envía eventos de ejemplo por stdin y valida la decisión y el código de salida.
Se conservan los casos docentes y se agregan herramientas/argumentos de Codex.
Ambas decisiones deben terminar con código 0: stdout vacío permite y JSON
hookSpecificOutput con PreToolUse, deny y motivo no vacío deniega.
Pasar este banco no demuestra que Codex haya cargado el hook.
"""
import json
from pathlib import Path
import subprocess
import sys

HOOK = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).with_name("proteger_env.py"))


def ev(herramienta, **campos):
    return {"hook_event_name": "PreToolUse", "tool_name": herramienta, "tool_input": campos}


# (descripción, evento, decisión esperada); el código de salida siempre debe ser 0.
BASICAS = [
    ("Leer .env", ev("Read", file_path=".env"), "deny"),
    ("Shell: cat .env", ev("Bash", command="cat .env"), "deny"),
    ("PowerShell: Get-Content .env", ev("PowerShell", command="Get-Content .env"), "deny"),
    ("Shell: ejecutar verificar_entorno.py", ev("Bash", command="python verificar_entorno.py"), "deny"),
    ("Leer README.md", ev("Read", file_path="README.md"), "allow"),
    ("Leer test_calculadora.py", ev("Read", file_path="test_calculadora.py"), "allow"),
    ("Editar calculadora.py", ev("Edit", file_path="calculadora.py", old_string="x", new_string="y"), "allow"),
    ("Shell: python -m unittest", ev("Bash", command="python -m unittest"), "allow"),
]

# Solo se envían como datos al script. Ninguna orden de esta lista se ejecuta.
CODEX = [
    ("Leer calculadora.py", ev("Read", file_path="calculadora.py"), "allow"),
    ("Codex: unittest discover", ev("exec_command", cmd="python -m unittest discover"), "allow"),
    ("Codex: Get-Content .ENV", ev("exec_command", cmd=r"Get-Content -LiteralPath .\.ENV"), "deny"),
    ("Windows: alias con punto final", ev("exec_command", cmd="Get-Content .env."), "deny"),
    ("Codex: ruta Windows absoluta", ev("read_file", path=r"C:\laboratorio\.env"), "deny"),
    ("Escribir .env", ev("Write", file_path=".env", content="FICTICIO=1"), "deny"),
    ("Copiar hacia .env", ev("copy_file", source="ejemplo.txt", destination=".env"), "deny"),
    ("Campo anidado .env", ev("custom", request={"files": [{"file_path": ".env"}]}), "deny"),
    ("Codex: aplicar parche .env", {
        "hook_event_name": "PreToolUse", "tool_name": "apply_patch",
        "tool_input": "*** Begin Patch\n*** Delete File: .env\n*** End Patch",
    }, "deny"),
    ("Parche: mencionar .env en documento", ev("apply_patch", input=(
        "*** Begin Patch\n*** Add File: ejemplo.md\n+No leer .env\n*** End Patch"
    )), "allow"),
    ("Edición: mencionar .env en documento", ev("Edit", file_path="ejemplo.md", new_string="No leer .env"), "allow"),
    ("Archivo .env.example permitido", ev("Read", file_path=".env.example"), "allow"),
    ("Codex: argumentos JSON como texto", {
        "hook_event_name": "PreToolUse", "tool_name": "exec_command",
        "tool_input": json.dumps({"cmd": "Get-Content .env"}),
    }, "deny"),
    ("Codex: shell persistente", ev("write_stdin", chars="Get-Content .env\n"), "deny"),
    ("Codex: envoltorio functions.exec", ev("functions.exec", code=(
        'await tools.exec_command({cmd: "Get-Content .env"})'
    )), "deny"),
    ("Codex: py -3 simulador", ev("exec_command", cmd=r'py -3 ".\verificar_entorno.py"'), "deny"),
    ("Codex: intérprete con ruta", ev("exec_command", cmd=(
        r'& "C:\Python\python.exe" "C:\laboratorio\verificar_entorno.py"'
    )), "deny"),
    ("Codex: ejecución directa script", ev("exec_command", cmd=r".\verificar_entorno.py"), "deny"),
    ("Windows: Start-Process simulador", ev("exec_command", cmd=(
        r"Start-Process -FilePath .\verificar_entorno.py"
    )), "deny"),
    ("Windows: Invoke-Item simulador", ev("exec_command", cmd=r"Invoke-Item .\verificar_entorno.py"), "deny"),
    ("Codex: comando compuesto", ev("exec_command", cmd=(
        "Get-Content calculadora.py; python verificar_entorno.py"
    )), "deny"),
    ("Codex: python -m simulador", ev("exec_command", cmd="python -m verificar_entorno"), "deny"),
    ("Leer código del simulador", ev("Read", file_path="verificar_entorno.py"), "allow"),
    ("Shell: leer código del simulador", ev("exec_command", cmd=(
        "Get-Content -LiteralPath verificar_entorno.py"
    )), "allow"),
    ("Codex: argv de simulador", ev("exec_command", argv=["python", "verificar_entorno.py"]), "deny"),
    ("Sonda inerte de integración", ev("exec_command", cmd=(
        "python .claude/hooks/proteger_env.py --prueba-bloqueo-inerte"
    )), "deny"),
    ("Evento incompleto: denegar", {}, "deny"),
]

# Casos para la auditoría (Reto 4): NO tienen resultado "correcto" obligatorio. Observa y explica.
AUDITORIA = [
    ("Shell: ruta armada por partes", ev("Bash", command="python -c \"print(open('.'+'env').read())\"")),
    ("Shell: comodín", ev("Bash", command="type .e*")),
    ("Shell: variable intermedia", ev("Bash", command="x=.e; y=nv; cat $x$y")),
]


def correr(evento):
    return subprocess.run(
        [sys.executable, HOOK], input=json.dumps(evento), capture_output=True,
        text=True, encoding="utf-8", timeout=10,
    )


def decision(resultado):
    if resultado.returncode != 0:
        raise ValueError("El hook terminó con código %s en vez de 0" % resultado.returncode)
    if resultado.stderr.strip():
        raise ValueError("El hook produjo una salida inesperada en stderr")
    if not resultado.stdout.strip():
        return "allow"

    respuesta = json.loads(resultado.stdout)
    if not isinstance(respuesta, dict):
        raise ValueError("La respuesta JSON debe ser un objeto")
    especifico = respuesta.get("hookSpecificOutput")
    if not isinstance(especifico, dict):
        raise ValueError("Falta hookSpecificOutput en la respuesta JSON")
    motivo = especifico.get("permissionDecisionReason")
    if (
        especifico.get("hookEventName") != "PreToolUse"
        or especifico.get("permissionDecision") != "deny"
        or not isinstance(motivo, str)
        or not motivo.strip()
    ):
        raise ValueError("La denegación JSON no cumple el contrato PreToolUse")
    return "deny"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    fallos = 0
    for titulo, casos in (("Básicas originales", BASICAS), ("Codex / regresión", CODEX)):
        print("== %s ==" % titulo)
        for desc, evento, esperado in casos:
            resultado = correr(evento)
            try:
                got = decision(resultado)
                ok = got == esperado
            except ValueError as error:
                got = "ERROR: %s" % error
                ok = False
            fallos += not ok
            print("%-5s %-40s esperado=%s obtenido=%s" % ("OK" if ok else "FALLA", desc, esperado, got))
    print("\n== Auditoría (informativo) ==")
    errores_protocolo = 0
    for desc, evento in AUDITORIA:
        try:
            got = decision(correr(evento))
            estado = "bloqueado (JSON)" if got == "deny" else "NO bloqueado: ¿por qué?"
        except ValueError as error:
            got = "ERROR"
            estado = str(error)
            errores_protocolo += 1
        print("%-40s obtenido=%s  (%s)" % (desc, got, estado))
    total = len(BASICAS) + len(CODEX)
    print("\nResultado: %s/%s pruebas obligatorias aprobadas" % (total - fallos, total))
    if errores_protocolo:
        print("Errores de protocolo en auditoría:", errores_protocolo)
    sys.exit(1 if fallos or errores_protocolo else 0)


if __name__ == "__main__":
    main()
