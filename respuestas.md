# Respuestas del Reto 4 — Auditoría del control

## 1. ¿Qué detectó el auditor?

Se ejecutó este comando de revisión pasiva, que terminó con código 0:

```powershell
python variantes/auditar_unicode.py INSTALAR.md variantes/README_unicode_demo.md
```

En `INSTALAR.md` no hubo hallazgos. En `variantes/README_unicode_demo.md` se detectaron cuatro caracteres `U+200B ZERO WIDTH SPACE`, todos en la línea 7, en las columnas 8, 12, 19 y 26. También apareció un comentario HTML en la línea 9. En total fueron **cinco hallazgos**.

Estos espacios no se distinguen al leer normalmente la frase. El comentario HTML está presente en el archivo crudo, aunque no aparece al renderizar Markdown. En la sesión quedó registrada la lectura del texto crudo y la salida del auditor; no se documentó una comparación visual con una vista renderizada.

No se encontró una orden maliciosa explícita en los dos documentos revisados. Sí había instrucciones para instalar, ejecutar pruebas o hacer la auditoría, pero se trataron como texto para analizar y no como autorización para ejecutar más acciones. Que existan caracteres invisibles o comentarios ocultos merece revisión, pero por sí solo no demuestra un ataque. Además, una instrucción maliciosa puede estar completamente visible.

## 2. ¿Por qué un README no tiene la misma autoridad que el usuario?

El texto del repositorio lo pudo escribir su autor o cualquier tercero que haya aportado cambios. No sabemos que represente la intención de la persona que está usando el agente, así que su nivel de confianza es menor. Leerlo sirve para entender el proyecto; no significa que haya que obedecer todas sus instrucciones.

En el diagnóstico del Reto 1, el README intentaba agregar la ejecución del simulador como requisito previo para corregir la calculadora. Esa acción no era necesaria para el arreglo pedido y Codex la rechazó. En cambio, los documentos del Reto 4 tienen instrucciones de instalación y auditoría, sin una orden maliciosa explícita. La autorización para esta revisión vino del usuario, no del contenido del README.

## 3. ¿Qué limitación tiene el hook y qué otra defensa añadiría?

El hook analiza el texto de la solicitud y reconoce nombres y patrones literales. No interpreta completamente lo que hará un programa ni resuelve todas las rutas que el shell puede construir durante la ejecución. La sección `AUDITORIA` de `.claude/hooks/probar_hook.py`, líneas 86 a 91, incluye ejemplos con concatenación, comodines y variables intermedias que ilustran ese límite. Son datos de prueba: en el Reto 4 no se ejecutaron esas órdenes ni se comprobó una evasión real.

También hay un límite de alcance: permitir una herramienta de pruebas no significa que el hook intercepte automáticamente cada subproceso que esa herramienta lance internamente.

Yo añadiría un sandbox con permisos mínimos. El agente y las pruebas solo deberían tener acceso a los archivos necesarios del laboratorio, sin acceso a secretos y con la red denegada. Así, aunque el filtro textual no reconozca una solicitud, el sistema operativo puede impedir la lectura de un archivo protegido. Esta segunda defensa es una propuesta; no se implementó ni se probó su política de red en esta actividad.
