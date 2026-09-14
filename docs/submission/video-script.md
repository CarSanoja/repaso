# Repaso — School Community Memory: recording script

Use [video-script.txt](video-script.txt) as the read-aloud copy. English narration: **519 words**. Target **4:20**, including brief screen pauses; the final video must stay below five minutes. Spanish directions are not spoken.

This script replaces the old silent, synthetic-slide preview. Record the actual deployed Telegram interaction and inspect its retained evidence in the AWS observer. Keep historical playback visibly labeled Replay. Do not present the local rehearsal as live Telegram.

Before recording, enter the observer access code off camera, hide personal identifiers, verify the two approaches and assessed count against the displayed records, and time one complete rehearsal. If the state differs, change the narration to match it.

## 00:00–00:25 · EL PROBLEMA

**Pantalla — no leer:** Mostrar el dashboard sin datos personales y sobreponer: “Venezuela · UNICEF, end-2025: 2.7M need educational support · 1.5M out of school”. Fuente en letra legible al pie; no usar fotos de menores ajenos.

A child asks for help. Tomorrow, somebody has to remember what happened today.

In Venezuela, UNICEF's report covering twenty twenty-five estimated that two point seven million children needed educational support, and one point five million were out of school. Community learning support needs continuity between the people helping and the families learning.

## 00:25–00:55 · EL COSTO DEL SEGUIMIENTO

**Pantalla — no leer:** Sobreponer “UNICEF Venezuela education response · 2025: US$23.7M required · 77% funding gap”. Pie: “UNICEF end-2025 report, Annex B, p.16”. Esta cifra es el requerimiento de esa respuesta humanitaria, no el costo económico total del problema ni ahorro atribuible a Repaso.

UNICEF's education response required twenty-three point seven million dollars in twenty twenty-five, with a seventy-seven percent funding gap. That is a real resource constraint. Every hour spent reconstructing scattered messages is time a facilitator cannot spend helping a learner.

Repaso turns school material, practice at home, and the memory of what happened into a record an adult can follow.

## 00:55–01:18 · CONTRIBUCIÓN TÉCNICA TEMPRANA

**Pantalla — no leer:** Mostrar brevemente las páginas públicas de Strands PR #4207 y #4208. Rótulo: “2 upstream bug-fix PRs submitted · Open”. Volver al dashboard. No decir merged ni arreglos aceptados por AWS.

Building this also led me to submit two upstream bug-fix pull requests to Strands Agents: one for reliable model identity in telemetry, and one for the model streaming interface. Both are open for review.

Repaso runs its agent workflows on Amazon Bedrock AgentCore. Here is what that engineering makes possible.

## 01:18–01:48 · DEL DÍA A LA CONVERSACIÓN

**Pantalla — no leer:** En el frontend AWS, seleccionar estudiante, fracciones y el día con evidencia. Mostrar gráfico diario y “Follow this day’s episode”. Abrir el tema y luego Replay; elegir la primera petición de ayuda. Telegram real a la izquierda; frontend a la derecha o mostrar el frontend completo para leer las tres columnas.

The family dashboard answers practical questions. Who practised? Which topic? How many different questions were assessed? When is a review due?

Select a day, then open its learning episode. The screen becomes three connected views: the conversation, the agent's recorded actions and memory, and the evidence for this topic.

This is the real Telegram interaction we recorded, linked to its stored AWS evidence.

## 01:48–02:40 · EL MOMENTO WOW

**Pantalla — no leer:** En Telegram mostrar las dos solicitudes y respuestas ya recibidas. En Replay seleccionar primero la explicación del pastel y después la de papel doblado. Mantener visibles la solicitud seleccionada y las cajas BEFORE/NOW del centro. Abrir los eventos vinculados solo 3–4 segundos. NO simular nuevos eventos ni presentar Replay como llegada en directo.

First, the learner asks for another explanation of equivalent fractions. Repaso explains with a cake and remembers the approach.

Then the learner says, “I still don't understand. Use another example.”

Watch the middle column. One previous approach was loaded. That retained approach is shown here. The new explanation uses folded paper, and its new approach is saved for the next turn.

The reply, the memory, and the delivery are connected by recorded identifiers. We can inspect that connection.

Two requests for help. Two remembered explanations. The assessed-answer count stays at three. Asking for help has not become a wrong answer.

## 02:40–03:16 · QUÉ EVIDENCIA EXISTE

**Pantalla — no leer:** Señalar preguntas distintas, intentos repetidos, dificultad y estimación actual. Volver al dashboard: mostrar el único día activo y alternar Daily/Cumulative. No mover el contador respondiendo una opción durante esta sección.

Now look at the learning evidence. Those three earlier assessments repeated the same question content. Repaso shows that limitation. Three correct answers to the same question do not establish learning improvement.

The chart has one day of observed activity. It does not invent a progress curve. Cumulative evidence shows the record growing; it is not a historical mastery score.

That makes the next question useful: can the learner apply the idea to different content?

## 03:16–03:45 · LA MEMORIA SOBREVIVE

**Pantalla — no leer:** Pulsar Verify saved memory. Mostrar el mensaje de nueva lectura y volver al episodio. Breve plano del diagrama existente de cuatro workflows o de eventos reales; no enseñar terminal con credenciales.

Read the memory again. The approaches are still there.

Strands coordinates material ingestion, practice planning, responses and daily review. DynamoDB preserves the evidence, while application rules control evaluations and state changes.

The gain demonstrated here is continuity: the next explanation can use what came before, and the adult can inspect the evidence behind it.

## 03:45–04:20 · PARA QUIÉN Y QUÉ SIGUE

**Pantalla — no leer:** Mostrar dashboard y cerrar con “Repaso · School Community Memory” y “The next step stays on record”. Añadir enlace público del proyecto cuando esté disponible. No mostrar logos de organizaciones como si fueran aliadas.

Our Good Neighbor proposal is a community facilitator supporting families between meetings, starting with fourth-grade mathematics.

The working demonstration is family scoped. A full school coordination workflow and a community pilot are next steps. We have not measured learning gains or staff time saved.

Repaso keeps a request for help connected to its history and its next action.

The conversation ends. The next step stays on record.

## Sources and claim boundaries

- [UNICEF end-2025 Venezuela report, page 6](https://www.unicef.org/media/178481/file/Venezuela-Humanitarian-SitRep-No.2-(End-of-Year),-31-December-2025.pdf.pdf): 2.7 million children needing educational support and an estimated 1.5 million out of school; published January 29, 2026. Annex B, page 16, gives education requirements of US$23,718,000 and a US$18,218,927 funding gap (77%); these describe the UNICEF response, not the total economic cost or savings from Repaso.
- [UNICEF Zulia field account](https://www.unicef.org/venezuela/en/stories/education-cannot-wait-programme-doesnt-stop-during-quarantine): work in June 2020, published March 3, 2021; 25 children per facilitator. The five-minute, five-day workload example is our explicit assumption: 625 minutes, or 10 hours 25 minutes weekly. No measured workload or savings are claimed.
- Strands contributions [#4207](https://github.com/strands-agents/harness-sdk/pull/4207) and [#4208](https://github.com/strands-agents/harness-sdk/pull/4208) were open, not merged, when verified September 14, 2026.
- National statistics are context, not Repaso's users. No UNICEF, school or nonprofit partnership is established. The community facilitator use case is proposed; deployed access remains family scoped.
- The two real help interactions and repeated-content assessments demonstrate adaptive help and durable evidence. They do not establish learning gains or staff time saved. The separate synthetic rehearsal of reduced practice is deliberately omitted from this recording path.
