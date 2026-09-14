# Prueba real de Telegram: 14 de septiembre de 2026

## Observación y diagnóstico

El usuario operó Telegram. A las 21:58 UTC, una petición de explicación llegó al
runtime. CloudWatch registró una llamada live que produjo `TurnDecision` y el
evento `turn.explanation`. La respuesta quedó confirmada por el transporte.
No había una práctica de hoy ni una sesión de estudio abierta: el bot contestó
que la cápsula llegaría a las 18:30. El contador permaneció en cero y no se guardó
una explicación. Este intento prueba recepción, clasificación y entrega, pero
no la escena de memoria del pitch.

El usuario inició `/tema fracciones equivalentes`. Entre las 21:59 y 22:00 UTC
abrió una sesión y respondió sus tres preguntas. Informó que las tres eran
iguales. La inspección confirmó tres IDs distintos, todos con el mismo enunciado
y las mismas opciones. Cada respuesta tenía su operación y recibos propios:
la repetición vino de la selección del banco, no de un reintento de Telegram.
El resultado 3/3 existe, pero no representa tres ejercicios distintos ni una
medición válida de mejora educativa.

## Correcciones

1. La selección de sesiones de estudio ahora descarta contenido idéntico aunque
   cambien los IDs, las mayúsculas, los espacios o el orden de las opciones.
   Las copias de preguntas excluidas por práctica reciente también se excluyen.
   Si solo queda una pregunta distinta, la sesión ofrece una y comunica que
   necesita más material. Esto no es deduplicación semántica de paráfrasis.
2. El observador incluye las entregas que el canal guarda bajo el chat, además
   de las guardadas bajo la familia. La pertenencia se comprueba en el resultado
   preparado del canal; una inscripción anterior del mismo chat no se mezcla.
   Esta corrección permitió mostrar los 20 eventos de entrega de la prueba.

## Verificación antes del despliegue

- 66 pruebas específicas de banco, estudio, canal y observador: correctas.
- Suite completa final: **2122 passed, 66 skipped**, 84,16 segundos.
- Imagen ARM64 de AgentCore: los cuatro pasos del ensayo y la selección sin
  duplicados se ejecutaron correctamente con las dependencias instaladas.
- Selección local sobre una lectura del banco real: tres contenidos distintos;
  no se modificaron los ítems de AWS para fabricar ese resultado.
- Diferencia de CloudFormation revisada: únicamente la imagen de
  `repaso-agentcore`, conservando `deployment_mode=ephemeral`, su configuración
  existente. La plantilla anterior se guardó fuera del repositorio.

## Despliegue y repetición

Actualización completada con CDK: `repaso-agentcore`, versión **12**, runtime
`READY`, endpoint `DEFAULT` también `READY` y `liveVersion=12`. CloudFormation
completó la actualización en 19,33 segundos; el proceso completo, incluida la
publicación de imágenes, tomó 102,12 segundos. La imagen usa la etiqueta
`308e796db2ae465b3b7a35bdc9103a4e9c0690d641f8b086799c1b50996f5a3d`.
El stack de API no se actualizó; CDK publicó sus assets como dependencia.

El observador AWS pasó una comprobación adicional en Chrome: 22 eventos
visibles, contador en 3, detalles de eventos conservados al refrescar y cero
errores JavaScript. Todavía falta verificar una petición de explicación durante
una sesión abierta con la versión nueva.

Se comprobó que no había una invocación activa mediante las leases de DynamoDB.
`StopRuntimeSession` terminó la sesión inactiva del chat con HTTP 200. Una
invocación de comprobación con un tipo no admitido levantó la nueva sesión y
devolvió HTTP 200 / `unknown_kind`, antes de construir servicios o ejecutar
handlers; no envió mensajes a Telegram. Esta prueba confirma el arranque y el
despachador, no una explicación del modelo.

Las sesiones de ejecución existentes pueden conservar el código anterior tras
actualizar AgentCore; hay que terminar la sesión de ejecución inactiva o usar
una nueva antes de verificar la corrección. La memoria de la aplicación se
conserva en DynamoDB. Referencias: [comportamiento de las sesiones al actualizar](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-troubleshooting.html)
y [StopRuntimeSession](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_StopRuntimeSession.html).

## Continuar la escena de memoria

Con la pregunta de la segunda sesión abierta, pedir una explicación y después
otra, sin iniciar una práctica adicional. Comparar las respuestas evaluadas
contra la base actual (3), no contra un cero preparado. Solo declarar verificado
el momento cuando aparezcan el contexto recuperado, la nueva nota persistida y
la entrega real correspondientes.

## Petición de explicación con la versión 12

A las 22:14 UTC, el usuario abrió otra sesión y pidió ayuda antes de responder.
El runtime cargó su contexto (`memory.explanation.context_loaded`), pero la
llamada `generate.structured_output` terminó en `guardrail_intervened` antes de
producir una explicación. Guardó la petición, con `explained` vacío, y entregó
el mensaje de indisponibilidad. Las respuestas evaluadas permanecieron en 3.

Una comprobación con la misma política publicada de Bedrock dio estos resultados:

| Contenido evaluado | Resultado observado |
| --- | --- |
| Frase de ayuda del usuario | `NONE` |
| Plantilla antigua de explicación con instrucciones dentro del mensaje de usuario | `GUARDRAIL_INTERVENED`, `PROMPT_ATTACK`, confianza `MEDIUM`, fuerza `HIGH` |
| Registro JSON de datos de la lección, con las instrucciones en el mensaje de sistema | `NONE` |
| Registro JSON con una petición de ignorar instrucciones y revelar el prompt | `GUARDRAIL_INTERVENED` |

La corrección de `explainer` v2 separa instrucciones de la aplicación y datos de
la lección. Todo el contenido de usuario sigue pasando por el filtro; se conserva
la misma política publicada, con sus filtros de entrada y salida. La clave,
justificación y opciones no se envían al explicador antes de responder; después
de responder conserva la justificación y el resultado evaluado.

Se realizaron llamadas reales a Sonnet con los filtros activos, sin enviar nada
a Telegram. Devolvieron explicaciones y etiquetas de enfoques distintas al
recibir el enfoque anterior. Esto comprueba la generación estructurada y el uso
del contexto, pero no garantiza que toda explicación mantenga la respuesta oculta:
una salida todavía adelantó una equivalencia. No prometer ese comportamiento
absoluto en el pitch.

También se corrigió el observador: una petición sin enfoque recordado ya no
incrementa «Explanations remembered». La petición queda visible, y el detalle de
la llamada muestra `guardrail intervened`. Chrome verificó ese estado real con
contador 0 y sin errores JavaScript. Las pruebas distinguen fallo de generación,
nota guardada y explicación recordada.

Referencia técnica: [Bedrock distingue instrucciones de sistema y entrada evaluada](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-use-converse-api.html).

## Corrección desplegada en la versión 13

La versión **13** y su endpoint `DEFAULT` quedaron `READY`, con `liveVersion=13`.
CloudFormation completó la actualización en 19,41 segundos; el despliegue completo
tomó 80,35 segundos. Se comprobó que no había leases activas, se terminó la sesión
de ejecución inactiva y se verificó el arranque nuevo con un tipo de evento no
admitido: HTTP 200 / `unknown_kind`, sin ejecutar handlers ni enviar a Telegram.
No se borraron notas ni resultados de la familia.

- Suite completa final: **2123 passed, 66 skipped**, 86,09 segundos.
- Imagen de ejecución: comprobación de los cuatro pasos del ensayo y de la
  selección de contenido sin duplicados, correcta.
- Recorrido adicional con filtros y modelos reales (Haiku para intención y
  Sonnet para explicación), almacenamiento y transporte locales: una petición
  fallida previa, primera explicación, segunda explicación con el enfoque anterior
  recuperado. Se guardaron dos enfoques distintos: pizza y barra de chocolate.
  El contador de respuestas evaluadas permaneció en cero; no se enviaron mensajes
  a Telegram. La primera salida adelantó la equivalencia: sigue vigente la
  limitación pedagógica indicada arriba.
- El primer intento de ese comprobador leyó la nota equivocada porque su reloj
  simulado asignaba la misma fecha a todas las notas. Se corrigió el comprobador
  para avanzar el reloj entre turnos; no fue un fallo del modelo ni un cambio
  adicional de producción.

## Primera explicación confirmada en Telegram con la versión 13

A las **22:30 UTC**, el usuario confirmó «explicó perfecto». La lectura de AWS
verificó el recorrido de esa petición:

1. Haiku produjo `TurnDecision` y se emitió `study_turn.explanation`.
2. `memory.explanation.context_loaded` recuperó **1 nota y 0 enfoques**: la nota
   anterior era la petición que había fallado, sin explicación retenida.
3. Sonnet produjo `Explanation` correctamente, en unos **3,88 segundos** de
   llamada de generación. Esta cifra no es latencia total de Telegram.
4. `memory.turn.saved` coincide con la referencia de la nueva nota persistida,
   cuyo enfoque es `same-size piece cake model`.
5. Los eventos de entrega confirmada están vinculados a esa invocación mediante
   `parent_correlation_id`.

El observador mostró **1 explicación recordada y 3 respuestas evaluadas**.
Pedir ayuda no sumó una respuesta ni un error. La petición fallida sigue visible
y no cuenta como explicación. Esto verifica la primera explicación de extremo
a extremo con el usuario operando Telegram y AWS como fuente del observador.
Chrome comprobó además el panel conectado y una nueva lectura mediante
**Verify saved memory**: conservó los contadores **3 / 1**, con eventos conectados
y sin errores JavaScript.

A las 22:30:31 UTC comenzó además una ejecución de práctica programada, con otra
correlación. No atribuir sus eventos a la explicación ni presentarlos como una
consecuencia de pedir ayuda.

## Segunda explicación: recuperación y cambio de enfoque confirmados

A las **22:32 UTC**, el usuario pidió otro ejemplo y confirmó que recibió uno
diferente. La lectura de AWS verificó:

- `memory.explanation.context_loaded`: **2 notas recuperadas y 1 enfoque previo**,
  antes de la llamada al explicador. Las dos notas incluyen la petición fallida.
- `generate.structured_output`: `Explanation` correcta con Sonnet, unos
  **4,92 segundos** de generación, con evidencia de llamada live.
- `memory.turn.saved`: nueva nota persistida, enfoque `paper strip folding`,
  distinto del anterior `same-size piece cake model`.
- Entregas confirmadas con el vínculo a la misma invocación.
- Contadores: **2 explicaciones recordadas, 3 respuestas evaluadas, 3 correctas**.

Queda verificado en Telegram y AWS el primer momento del pitch: el agente recibe
la petición, recupera el enfoque usado, genera otro y guarda la nueva experiencia
sin evaluar la petición de ayuda como una respuesta. La evidencia muestra contexto
recuperado y un cambio observado; no es una medición de aprendizaje ni una garantía
de que todo ejemplo futuro será diferente.

**Frase para el video:** “Repaso remembers the approach it already tried. When the
learner asks again, it loads that memory and offers another example. Asking for
help never became a wrong answer in this exchange.”

**Siguiente comprobación:** responder una opción de la pregunta abierta y verificar
el cambio **3 → 4** en respuestas evaluadas. La decisión adulta que cambia una
práctica futura sigue requiriendo su propia prueba real; no queda validada por
estas dos explicaciones.
