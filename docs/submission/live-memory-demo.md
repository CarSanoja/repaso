# Demo de Telegram, memoria y eventos

Especificación original del 14 de septiembre de 2026. El observador y un ensayo
aisladamente reproducible ya están implementados: usar el
[guion y estado de validación actuales](memory-demo-runbook.md). Las propuestas
de coordinación grupal que aparecen abajo siguen siendo alcance futuro.
El usuario maneja Telegram; el observador AWS es de lectura.

## Lo que el espectador debe comprender

**Un mensaje produce una observación persistente; esa observación participa en
una decisión; la decisión produce un siguiente paso verificable.**

La segunda pantalla es el espacio de seguimiento de un facilitador. Muestra la
memoria útil y su procedencia. La telemetría explica cómo se ejecutó el trabajo
en un detalle secundario. No muestra razonamiento privado del modelo: muestra
salidas estructuradas, registros y decisiones del sistema o del adulto.

## Composición de las dos pantallas

| Zona | Contenido | Fuente |
| --- | --- | --- |
| Telegram | Chat real del caso sintético, preguntas, respuesta del usuario y botones | Bot desplegado |
| Grupo | Familias autorizadas y observaciones pendientes; identificar historial preparado | Estado persistido |
| Memoria del caso seleccionado | Último intento, explicación usada, resultado/revisión, decisión activa y próxima práctica | Registros del caso |
| Qué acaba de cambiar | Antes → después, hora de observación y enlace a la evidencia | Cambio de estado comprobado |
| Actividad | Interpretación, nodo ejecutado, llamada terminada, envío intentado/confirmado | Eventos instrumentados |
| Detalle opcional | Rol/modelo, duración, tokens y costo cuando se reportaron | Traza/ledger |

Una selección de familia debe controlar toda la vista. El espectador debe poder
relacionar lo que escribió con lo que cambió sin leer JSON ni identificadores
largos. El detalle técnico conserva los identificadores necesarios para auditar.

## Secuencia sugerida: 2–3 minutos

Los tiempos son editoriales, no objetivos de latencia ni mediciones del producto.
Las salidas del modelo se observarán; no se promete un texto exacto.

| Momento | Acción | Memoria / evento que queremos observar | Afirmación defendible |
| --- | --- | --- | --- |
| 0:00–0:20 | Presentar al facilitador y su grupo sintético | Estado inicial y una fuente del problema | Caso inspirado en un trabajo comunitario documentado |
| 0:20–0:45 | Enviar una hoja o abrir una práctica ya preparada, claramente indicado | Material revisado y sesión existente | La práctica tiene un origen identificable |
| 0:45–1:10 | Escribir «No entiendo, explícamelo de otra forma» en una sesión abierta | Intención de pedir explicación; explicación registrada; intentos evaluados sin aumentar | Pedir ayuda conserva su significado y no se convierte en una respuesta incorrecta |
| 1:10–1:35 | Responder al ejercicio | Resultado o revisión pendiente, episodio/turno y progreso aplicables a esta ruta | La observación se conserva con su contexto |
| 1:35–2:05 | Abrir una dificultad compartida de tres familias sintéticas | Evidencia por caso, con fechas; historia preparada identificada | Un facilitador puede inspeccionar una necesidad del grupo |
| 2:05–2:35 | Revisar y confirmar una intervención que esté implementada | Decisión persistida y efecto real en la familia | La decisión humana modifica el siguiente paso |
| 2:35–3:00 | Mostrar la nueva práctica o el envío y refrescar la vista | Cambio leído de almacenamiento y estado de entrega | El resultado persiste fuera del chat |

Si la intervención del coordinador no está terminada, mostrar la decisión adulta
que sí existe y declarar ese alcance. No simular un botón docente que no ejecuta
nada. El video final se ajustará al recorrido que pase las comprobaciones.

La escena de explicación merece una comprobación específica: comparar los
intentos antes/después. La escena de cierre debe mostrar un cambio registrado,
no únicamente que un botón fue pulsado. Recargar la página prueba persistencia
del estado mostrado; no prueba por sí sola recuperación del runtime.

## Memoria que existe en el código

| Memoria | Código | Límite relevante |
| --- | --- | --- |
| Contexto de conversación | `core/orchestration/turn_memory.py` | Ventana de ocho notas; no es recuerdo ilimitado |
| Enfoques de explicación ya utilizados | `study_context.py`, `turn_memory.tried_approaches` | Se proporcionan al explicador; comprobar el comportamiento real, no garantizar que nunca repita |
| Intentos de estudio | `tools/episode_log.py`, `schemas/episode.py` | Incluye resultado, revisión y quién evaluó; comprobar qué rutas escriben episodios |
| Progreso y estado de sesión | `schemas/session.py`, `schemas/study_session.py` | Cápsulas y sesiones de estudio son rutas distintas |
| Evidencia y decisiones adultas | `schemas/escalation.py`, resolución de cuarentena | Distinguir propuesta, decisión y ejecución |
| Trabajo pendiente y repetición | `runtime/entrypoint.py`, registros de operación | Estado durable de la aplicación, no memoria conversacional del modelo |
| Entrega | `core/orchestration/outbox.py` | Recibos de transporte; no prueban lectura humana |

Las notas de turno tienen caducidad de siete días y se elimina el texto de la
familia al cerrar su ventana. No generalizar esa caducidad a todo registro:
la revisión de seguridad documenta una excepción pendiente en cuarentena.

## Instrumentación ya disponible

- `TraceEvent` contiene fecha, tipo, nombre, estado, duración y campos extra.
- El runtime añade un `correlation_id` derivado de la invocación.
- Los nodos emiten eventos `node` de inicio, finalización y fallo.
- El lector emite `turn` o `study_turn` con la intención interpretada.
- `InstrumentedModel` registra llamadas y uso reportado por el proveedor.
- La outbox emite `delivery.attempted`, `delivery.failed` y
  `delivery.acknowledged` usando su propio identificador de correlación.
- `CloudWatchTelemetrySink` escribe trazas estructuradas y elimina identificadores
  de familia/estudiante del log publicado.
- `scripts/reconstruct_cloud_journey.py` ya lee trazas de CloudWatch;
  `scripts/command_center.py` muestra telemetría local en terminal.
- `/judge/students` y `/judge/transcript/{family_id}` ofrecen datos de familias
  explícitamente permitidas mediante código. No son un sistema completo de roles
  para docentes y no exponen todavía toda la memoria de estudio.

## Brechas técnicas a resolver antes de dibujar la cadena

1. **Lectura autorizada.** Restringir el observador a casos de demostración
   permitidos o a miembros del grupo del coordinador. Credenciales AWS y códigos
   de acceso nunca se dibujan ni se incluyen en el video o URLs públicas.
2. **Eventos frente a estado.** No hay una traza general por cada escritura de
   memoria. Un observador puede mostrar diferencias entre lecturas autorizadas
   con la etiqueta «cambio observado». Para afirmar «esta operación escribió
   este registro», añadir instrumentación con procedencia explícita.
3. **Correlación entre componentes.** El ID del runtime y el de la outbox no son
   el mismo. No unirlos solo por cercanía temporal. Incorporar una relación padre
   en los eventos nuevos o una relación verificable en el registro de operación.
   Mantener IDs opacos; no reintroducir identificadores infantiles en logs.
4. **Recepción real.** No existe evidencia aquí de que cada tramo webhook →
   EventBridge → SQS → runtime tenga su propio evento correlacionado disponible
   para la interfaz. Verificar cobertura y añadir solo lo necesario. No iluminar
   etapas que no se observaron.
5. **Latencia de observación.** CloudWatch puede llegar con retraso. Mostrar última
   actualización, hora del evento y estado «esperando eventos»; el silencio no
   significa ausencia de trabajo ni fallo. Paginar y deduplicar lecturas.
6. **Coordinación humana.** El rol docente y la aprobación que vuelve a las
   familias son trabajo nuevo. La nota grupal existente se canaliza por un padre.

## Regla visual: el movimiento representa evidencia

Se puede resaltar brevemente una tarjeta cuando se observa un cambio real y
animar la aparición de un evento. No generar actividad por temporizador ni
representar estados inventados para que la pantalla parezca viva.

- «Iniciado» exige un evento de inicio; «terminado», su resultado observado.
- «Entregado» debe precisar el acuse del transporte; «leído» requiere evidencia
  adicional que este canal no ofrece aquí.
- «Sin respuesta observada» conserva la incertidumbre; no atribuir abandono,
  desinterés, pobreza o falta de dominio a partir del silencio.
- Una decisión pendiente y un fallo son estados visibles; no esconderlos.
- Evidencia en vivo, historial preparado y replay llevan etiquetas diferentes.
- Los costos sin datos se muestran como no reportados, nunca como cero.
- Identificar decisiones de reglas, del modelo y del adulto por separado.

## Criterios de aceptación

1. Un mensaje escrito por el usuario se vincula al caso correcto y al evento
   real que lo procesa; no hay mezcla con otro grupo.
2. La petición de explicación deja intacto el contador de respuestas evaluadas.
3. Una respuesta modifica únicamente los registros previstos para su ruta.
4. El panel puede leer la decisión persistida y mostrar su efecto real.
5. Los eventos de entrega y el estado final coinciden con lo visible en Telegram.
6. Un refresco conserva las observaciones almacenadas; los errores de lectura se
   indican y no dejan una pantalla obsoleta etiquetada como actual.
7. Ninguna unión visual entre eventos depende solo del orden o de la proximidad
   de sus fechas.
8. La grabación y los materiales explican el alcance comunitario implementado y
   señalan los datos sintéticos y los saltos de tiempo.

## Prioridad de construcción

Primero, conectar el observador a una familia sintética y probar Telegram →
evento → cambio persistido → efecto. Después, añadir la vista de grupo y una
intervención autorizada completa. Por último, pulir transiciones, grabar y cerrar
la entrega. El límite de publicación debe protegerse reduciendo alcance si hace
falta; no se sustituye una función incompleta por una animación.
