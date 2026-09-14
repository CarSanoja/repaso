# Repaso: demostración grabable de memoria y seguimiento

Implementado y probado localmente el 14 de septiembre de 2026. Este documento
sustituye la secuencia propuesta en `live-memory-demo.md` para lo que se puede
ensayar hoy. El usuario opera Telegram.

**Interfaz actual:** el [guion de episodios](episode-demo-runbook.md) describe la
nueva entrada por tema, las tres columnas sincronizadas y Live/Replay. Este
documento conserva la explicación de los cuatro momentos y sus límites.

## Qué mostrar y qué decir

**La promesa del pitch:** «Una familia pide ayuda. Repaso conserva lo que ocurrió
y convierte una decisión del adulto en la siguiente práctica».

**Frase de apertura en inglés:**

> A community educator may support many families through messages. Who remembers
> what each child tried, what helped, and what should happen next? Repaso makes
> that follow-through visible.

El caso comunitario y sus fuentes están en [good-neighbor-case.md](good-neighbor-case.md)
y [pitch-research.md](pitch-research.md). Es un caso de uso propuesto, inspirado
en trabajo documentado. No existe una alianza con UNICEF ni un piloto medido.
No afirmar que ya hay un portal docente con intervención grupal: el observador
muestra familias permitidas; el flujo de decisión implementado es el del adulto.

## Los cuatro momentos

| Momento | Acción | Evidencia visible | Narración sugerida |
| --- | --- | --- | --- |
| 1. La ayuda tiene memoria | Pedir una explicación y luego otra | Respuestas evaluadas siguen en 0; aparecen dos enfoques. En la instrumentación nueva, `explanation.context_loaded` muestra 1 enfoque previo antes de la segunda llamada | “Asking for help did not become a wrong answer. The next explanation receives what we already tried.” |
| 2. La respuesta deja evidencia | Responder la pregunta | Respuestas evaluadas 0 → 1; evento y registro guardado | “Now there is an actual answer. That becomes learning evidence.” |
| 3. La decisión cambia lo que sucede | Elegir menos práctica en una decisión adulta existente | Decisión resuelta, adaptación vigente, próxima cápsula 3 → 1 pregunta | “The adult chooses a lighter load. The next scheduled practice actually changes.” |
| 4. El chat no es el único lugar donde vive el seguimiento | Pulsar **Verify saved memory**, después recargar y volver a conectar | Una nueva lectura conserva notas y decisiones | “Close the screen. The follow-through stays.” |

El ensayo prepara la decisión adulta y avanza un día con reloj simulado. Ambas
cosas se identifican en pantalla. No afirmar que dos peticiones de ayuda causaron
esa decisión ni que transcurrió un día real. En AWS la práctica siguiente depende
del flujo y reloj reales. Se necesitan sus registros antes de grabar ese momento.
La relectura prueba persistencia; no prueba reinicio ni recuperación de AgentCore.

**Base real de la prueba del 14 de septiembre:** las respuestas evaluadas ya estaban
en **3**. Las dos explicaciones se verificaron en Telegram y AWS: el contador se
mantuvo en **3**, el agente recuperó **1 enfoque previo** y las explicaciones
recordadas pasaron de **1 a 2**. Para esa grabación, usar **3 → 4** al responder,
en lugar de los valores **0 → 1** del ensayo. No reiniciar datos para aparentar
una prueba nueva.

## Arrancar la segunda pantalla

Desde la raíz del repositorio, con las dependencias de desarrollo instaladas:

```bash
.venv/bin/python scripts/run_memory_observer.py --rehearsal --port 8870
```

Abrir <http://127.0.0.1:8870/judge/memory/>. Código local: `REPASO-VIEW`.
Pulsar los cuatro controles en orden y después **Verify saved memory**. Los
controles completados se deshabilitan. Recargar conserva los datos; para empezar
un ensayo limpio, detener este proceso con Ctrl+C y volver a ejecutar el comando.
Cada arranque usa un directorio temporal aislado.

Para observar AWS:

```bash
.venv/bin/python scripts/run_memory_observer.py \
  --family-id ID_DE_LA_FAMILIA_AUTORIZADA \
  --profile quanta --region us-east-1 --port 8767
```

Abrir <http://127.0.0.1:8767/judge/memory/>. Se puede cambiar el código local con
`--code`. El proceso solo escucha en loopback. No es una URL pública para jueces.
La familia debe existir y contener un estudiante para aparecer en el selector.
No poner códigos o identificadores personales en la grabación pública.

El observador AWS consulta DynamoDB y CloudWatch. No envía mensajes a Telegram.
El arranque no modifica la configuración del bot ni despliega el código nuevo.
La primera lectura establece la base: los cambios anteriores no se animan como
si acabaran de ocurrir. Las consultas se repiten tres segundos después de terminar
la lectura anterior; CloudWatch puede añadir más demora.

## Secuencia en Telegram: operada por el usuario

1. Usar una familia de demostración con un solo estudiante, material aprobado y
   preguntas de fracciones disponibles. Iniciar ambos encuadres antes de escribir.
2. Escribir `/tema fracciones equivalentes`. Debe aparecer una práctica abierta
   con una pregunta. `/sesion` abre o retoma una sesión sin elegir otro tema.
   Si el bot pide material, resolver ese paso primero; no interpretar su respuesta
   como una práctica ya abierta.
3. Escribir «no entiendo, explícamelo de otra forma». Esperar la respuesta y la
   nueva nota del observador. Comparar el contador de respuestas evaluadas.
4. Escribir «sigo sin entender, usa otro ejemplo». Inspeccionar el segundo enfoque.
   En AWS, mostrar solo los eventos que emita la versión desplegada.
5. Responder con una opción realmente ofrecida. Mostrar el aumento del contador.
6. Si existe una decisión adulta de reducir carga, resolverla desde Telegram y
   mostrar la adaptación. Si no existe, grabar ese momento como ensayo separado,
   con la etiqueta de simulación, o retirarlo del tramo en vivo.
7. Verificar memoria guardada. Recargar, conectar y mostrar la misma evidencia.

No usar `/listo` antes de enseñar las frases retenidas: cerrar la ventana borra
el texto `said` por diseño. Las notas expiran a los siete días; no son memoria
ilimitada. El contador de explicaciones refleja notas retenidas.

## Montaje de 2:30-3:00

- **0:00-0:20:** un facilitador comunitario y el problema de acompañar a varias
  familias. Usar una cifra con fuente, fecha y población, tomadas del dossier.
- **0:20-0:40:** Telegram junto al observador; indicar que el material está preparado.
- **0:40-1:25:** ayuda → memoria → otro enfoque. Mantener visible el contador base
  (3 en la prueba AWS del 14 de septiembre; 0 en un ensayo nuevo).
- **1:25-1:45:** respuesta → contador base + 1. Acercar el encuadre a la evidencia.
- **1:45-2:20:** decisión adulta → plan más ligero. Identificar el historial
  preparado y cualquier salto de reloj o segmento de ensayo.
- **2:20-2:40:** nueva lectura y cierre: “A conversation becomes a next step.”

La interfaz está en inglés; Telegram puede estar en español con subtítulos en
inglés. Evitar enumerar infraestructura durante la escena humana. Abrir un solo
**Inspect event** para mostrar el modelo, la correlación y los enfoques recibidos.
Los detalles abiertos permanecen abiertos durante las actualizaciones.

## Qué está implementado

- Vista de notas, decisiones, adaptaciones, prácticas y recibos de transporte.
- Comparación antes/después con indicadores que cambian al leer datos nuevos.
- Acceso por código y lista explícita de familias; notas vencidas excluidas.
- Eventos filtrados por familia o correlación verificada en sus operaciones.
- Estado de error y recuperación, sin presentar datos viejos como conectados.
- `memory.turn.saved`, `memory.adaptation.saved` y
  `memory.explanation.context_loaded` en el código nuevo.
- `parent_correlation_id` en la entrega nueva: vínculo explícito con la invocación.
- Ensayo con la lógica real de la aplicación, modelos de respuesta programada,
  transporte local y reloj simulado. No mide calidad ni latencia de Bedrock.

La instrumentación se desplegó en la versión **12** de AgentCore; la versión
**13** corrige el bloqueo del explicador durante la prueba con el usuario. Ver el
[registro actualizado](memory-live-check-2026-09-14.md). El observador muestra
cambios guardados y eventos disponibles. No dibuja un evento de recepción por
cada tramo de la infraestructura: esa cobertura no está instrumentada de extremo
a extremo.

## Validación ejecutada

- Suite completa tras las correcciones del banco y del explicador:
  **2123 passed, 66 skipped**, 86,09 segundos. Las pruebas live optativas no
  quedaron certificadas por esta ejecución local.
- Suite específica final `tests/api/test_memory.py`: **14 passed**. Incluye los
  cuatro momentos, pasos repetidos, aislamiento entre familias, acceso,
  caducidad, fallos de almacenamiento/logs, paginación y deduplicación de eventos,
  entregas bajo el chat y peticiones sin explicación que no incrementan el contador.
- Chrome con Playwright: código erróneo/correcto, cuatro pasos, relectura,
  recarga, escritorio 1440 px y móvil 390 px sin desbordamiento horizontal,
  interrupción de almacenamiento, recuperación y desconexión; sin errores JS.
- `ruff check`, `node --check`, `git diff --check` y revisión de secretos.
- AWS: almacenamiento y eventos accesibles; versión 13 activa. Los intentos reales
  y la prueba adicional con modelos reales y almacenamiento local están en el
  [registro de la prueba](memory-live-check-2026-09-14.md). Dos explicaciones
  exitosas por Telegram confirmadas en la versión 13: recuperación de un enfoque
  previo, nuevo enfoque guardado, entregas correlacionadas y contador real en 3.

La captura [memory-observer-rehearsal.png](assets/memory-observer-rehearsal.png)
muestra la aplicación durante la prueba local con familia sintética.

Comandos de verificación:

```bash
REPASO_LOCAL_MODE=true .venv/bin/pytest -q
.venv/bin/pytest -q tests/api/test_memory.py
.venv/bin/ruff check .
node --check src/repaso/api/static/memory.js
.venv/bin/python scripts/check_repo_hygiene.py
git diff --check
```

## Seguimiento de la prueba real

El usuario ya inició una práctica en Telegram. Se encontraron copias de la misma
pregunta en el banco y entregas que el observador omitía. Ver el
[diagnóstico, correcciones y validación posteriores](memory-live-check-2026-09-14.md).
Las cifras y el estado de despliegue de ese registro posterior prevalecen sobre
la lectura inicial de control descrita arriba.

## Antes de decir «listo para enviar»

Falta verificar el recorrido nuevo manejando Telegram, grabar el video final y
cerrar los requisitos de publicación de Devpost. El observador y el ensayo están
construidos; eso no equivale a una prueba integral de la versión desplegada ni a
un sistema docente completo. El objetivo de este guion es hacer visible lo que
se demuestra y mantener esas afirmaciones comprobables.
