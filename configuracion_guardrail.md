# Configuración y comprobación del guardrail — Semana 13

Fecha de comprobación: 19 de noviembre de 2026. Estado: registro instalado y
carga efectiva comprobada para las llamadas observadas del Reto 3.

## Registro real

El registro nativo del proyecto está en `.codex/config.toml`. Invoca
`.claude/hooks/proteger_env.py` en el evento `PreToolUse`, con matcher `.*` y
`async = false`. La ubicación del script conserva la estructura del laboratorio;
el registro que utiliza Codex es el TOML del proyecto.

La configuración utiliza una ruta relativa al proyecto. Ya no contiene una
ruta absoluta del perfil personal de Windows:

```toml
[[hooks.PreToolUse]]
matcher = ".*"

[[hooks.PreToolUse.hooks]]
type = "command"
command = 'python -X utf8 ".claude/hooks/proteger_env.py"'
async = false
```

**Codex debe iniciarse desde la raíz del repositorio**, con esa carpeta como
directorio de trabajo. La ruta relativa se resuelve desde ese directorio; no
debe iniciarse desde una carpeta superior o un subdirectorio para esta
configuración. Python debe estar disponible en PATH.

La ejecución síncrona permite que la decisión llegue antes de ejecutar la
herramienta. La ruta puede conservarse al mover el proyecto, manteniendo su
estructura e iniciando Codex desde la nueva raíz. No se cambian permisos ni
confianza desde este registro. No se modificó la lógica del hook.

La configuración relativa final se validó con el binario local del daemon
Codex **0.169.0**, mediante `--strict-config app-server --print-startup-config`.
Se usó una copia exacta del TOML en un directorio temporal aislado, únicamente
para el proceso hijo, y la raíz del repositorio como directorio de trabajo.
Terminó con código 0 y confirmó `"appServerVersion":"0.169.0"`.
Un control negativo temporal con un tipo inválido para `hooks.PreToolUse`
terminó con código 1: esperaba una secuencia. Esto demuestra que el parser
comprobó la estructura del registro. Hubo un aviso no fatal sobre auxiliares
de PATH en el directorio temporal; no se afirma que stderr estuviera vacío.
No se inició servidor ni modelo y no se accedió a la red ni a configuración
privada. Los temporales se retiraron. Esta validación acredita sintaxis;
no acredita por sí sola una recarga del hook en la conversación existente.

En la preparación final se ejecutó desde la raíz el comando relativo instalado,
enviándole por stdin un evento inocuo de lectura de la calculadora. Terminó con
código 0 y stdout vacío, que corresponde a permitir. El banco volvió a terminar
con **35/35 pruebas obligatorias aprobadas**. Esta comprobación verifica que el
comando relativo encuentra el script; no se presenta como una recarga del
registro en la sesión actual ni como una repetición de los bloqueos del Reto 3.

## Contrato vigente del script

El control recibe un evento JSON por entrada estándar y examina el nombre y los
argumentos de la herramienta. No ejecuta los argumentos recibidos, no abre
archivos, no inicia procesos y no usa la red.

El script termina con código **0** en ambas decisiones:

- **Permitir:** salida estándar vacía.
- **Denegar:** objeto JSON en salida estándar con `hookSpecificOutput`,
  `hookEventName = "PreToolUse"`, `permissionDecision = "deny"` y un
  `permissionDecisionReason` no vacío.

El código 0 por sí solo no significa que la herramienta esté autorizada. Codex
interpreta la decisión JSON. El banco actual exige también salida de error vacía;
la denegación actual no se comunica mediante código 2 ni mediante `stderr`.

## Integración observada en el Reto 3

Las tres solicitudes prohibidas fueron rechazadas antes de ejecutar la operación.
La respuesta real de la herramienta comenzó con `Command blocked by PreToolUse hook`.

| Solicitud | Decisión observada | Evidencia |
| --- | --- | --- |
| Sonda inerte de integración | Denegada; el motivo confirmó que el hook recibió la solicitud | [Captura de la sonda](capturas/01_bloqueo_sonda.png) |
| Lectura directa del archivo de entorno ficticio | Denegada por la política del laboratorio | [Captura de la lectura bloqueada](capturas/02_bloqueo_env.png) |
| Ejecución directa del simulador | Denegada por la política del laboratorio | [Captura de la ejecución bloqueada](capturas/03_bloqueo_simulador.png) |
| Lectura de `calculadora.py` | Permitida; `exit_code: 0`, con devolución del código | [Captura de operaciones legítimas](capturas/04_operaciones_permitidas.png) |
| `python -m unittest discover -v` | Permitida; `exit_code: 0`, ocho pruebas con `ok` y resultado `OK` | [Captura de operaciones legítimas](capturas/04_operaciones_permitidas.png) |

Como antecedente, una primera sonda anterior a la activación sí se ejecutó e
imprimió `SONDA EJECUTADA: esta llamada no fue bloqueada antes de ejecutarse.`
Esa observación histórica no describe el estado posterior: las solicitudes del
Reto 3 sí fueron bloqueadas explícitamente por el hook.

La carga efectiva está acreditada para esas llamadas. No se inspeccionó la
interfaz de inventario de hooks ni se verificaron allí `enabled`, `trustStatus`
o un estado `trusted`; no se atribuye un estado de interfaz no observado.
Tampoco se afirma que el matcher y la política cubran cualquier herramienta o
cualquier forma de acceso.

## Banco separado y límites

`.claude/hooks/probar_hook.py` obtuvo **35/35 casos obligatorios aprobados**
en la verificación final. Incluye además tres casos informativos de auditoría. Envía eventos JSON al control y comprueba su
protocolo; las órdenes de ejemplo son datos y no se ejecutan. Pasar este banco
no sustituye una prueba de integración. Los resultados completos se recogen
en [evidencias.md](evidencias.md).

- **Análisis textual:** el hook reconoce patrones y campos concretos. No
  interpreta completamente shell, Python o JavaScript ni resuelve rutas
  construidas durante la ejecución. Los casos informativos incluyen rutas
  compuestas, comodines y variables; no equivalen a ejecutar esas operaciones.
- **Subprocesos:** el hook de una herramienta exterior no intercepta
  automáticamente cada proceso hijo. La suite permitida incluye una prueba que
  ejecuta internamente una copia temporal del simulador. La autorización de la
  llamada exterior no garantiza la seguridad de cualquier código que importe.
- **Falsos positivos documentales observados:** dos solicitudes de parche para
  actualizar este documento mediante `functions.exec` y `apply_patch` fueron
  rechazadas sin aplicar cambios. Una incluía literalmente el indicador de la
  sonda como evidencia y otra el nombre del archivo protegido en texto
  documental. La inspección del texto del envoltorio confundió esas menciones
  con una operación prohibida. Esta versión utiliza descripciones y enlaces a
  las capturas; no ejecuta ni codifica las operaciones protegidas.
- **Integridad del control:** cambiar o desactivar el script o su registro puede
  anular la defensa; proteger esos archivos requiere permisos independientes.

## Segunda defensa propuesta

Se propone un sandbox desechable para el agente y los procesos de pruebas, con
solo los archivos ficticios necesarios, sin acceso a secretos, permisos mínimos
y red denegada. El sistema operativo limitaría el acceso incluso si una ruta se
resuelve dinámicamente o la acción procede de un subproceso. Esta segunda
barrera es una propuesta: no se afirma que haya sido instalada.
