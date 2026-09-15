# School Community Memory: three-minute video script

**Target 2:40. Maximum 3:00. English narration: 317 words.** This replaces the former four-minute script. Read at approximately 125-135 words per minute and reserve brief pauses for screen changes.

Use [video-narration.txt](video-narration.txt) for voice generation. Use [video-script.txt](video-script.txt) for recording instructions. Spanish screen directions are not spoken.

Record the actual Telegram interaction and its retained AWS evidence. Preserve the Replay label for past turns, hide personal identifiers and verify the displayed counts. Any public self-service rehearsal must be identified as synthetic on screen. Use the verified public demo URL in the closing caption: https://mwn2zjxcm2sz7jtrpj3y6ttblq0svgru.lambda-url.us-east-1.on.aws/judge/memory/ Access code: REPASO-LIVE.

## 00:00-00:25 | EL PROBLEMA

**Pantalla, no leer:** Mostrar dashboard y rótulo: UNICEF Venezuela, 2025. 2.7M necesitan apoyo educativo; 1.5M fuera de la escuela. Educación: US$23.7M requeridos, brecha 77%. Fuente al pie: UNICEF end-2025 report, pp.6,16. Son cifras de contexto y de esa respuesta humanitaria, no ahorro de Repaso.

Tomorrow's explanation should remember today's struggle.

In Venezuela, UNICEF's twenty twenty-five report estimated two point seven million children needing educational support and one point five million out of school. Its education response required twenty-three point seven million dollars, with a seventy-seven percent funding gap.

## 00:25-00:43 | CONTRIBUCIÓN Y PROPUESTA

**Pantalla, no leer:** Mostrar PR #4207 y #4208 durante 3 segundos, con rótulo: Two upstream Strands PRs submitted. Both open. Volver al producto. No afirmar merged, endorsement ni alianza AWS.

We built Repaso, School Community Memory, to keep learning support connected between meetings.

Building it also led to two upstream Strands Agents bug-fix pull requests, covering model telemetry and streaming compatibility. Both remain open for review.

## 00:43-01:05 | DEL DASHBOARD AL EPISODIO

**Pantalla, no leer:** Seleccionar estudiante, fracciones y día con evidencia. Pulsar Follow this day’s episode. Mostrar las tres columnas. Telegram real al lado; ampliar frontend para que se lea. Conservar REPLAY al reconstruir los mensajes ya registrados.

Start with a family, a topic and a day. See assessed answers, distinct questions and stored review dates.

Open the episode. Three synchronized columns reveal the retained conversation, the agent's actions and memory, and the learning evidence. This is our recorded Telegram interaction, connected to its AWS records.

## 01:05-01:50 | EL MOMENTO WOW

**Pantalla, no leer:** En Telegram mostrar las dos peticiones y respuestas reales. En Replay elegir primero pastel y luego papel doblado. Mantener visibles la petición seleccionada, BEFORE, NOW y el contador 3. No enviar mensajes nuevos para intentar recrear la historia durante esta toma.

The learner asks for help with equivalent fractions. Repaso explains with a cake and remembers that approach.

Then: “I still don't understand. Use another example.”

Watch the memory column. One previous approach was retrieved. The new explanation uses folded paper. Its approach is saved, and the reply is linked to its delivery record.

Two successful help requests. Two remembered explanations. The assessed-answer count stays at three. Asking for help does not become a wrong answer.

Select either message. The evidence follows that exact turn.

## 01:50-02:20 | EVIDENCIA Y ARQUITECTURA

**Pantalla, no leer:** Señalar una pregunta distinta frente a tres respuestas evaluadas. Pulsar Verify saved memory. Mantener el mensaje de nueva lectura. Breve rótulo: Strands Agents, AgentCore Runtime, DynamoDB. No sustituir datos reales con el ensayo sintético.

Those three earlier answers repeated one question. They do not prove learning improvement.

Read the memory again. It persists.

Strands coordinates the agent workflows on Amazon Bedrock AgentCore. Four workflows handle material intake, practice planning, responses and daily review, with explicit state transitions. DynamoDB preserves application memory and learning evidence. The demonstrated gain is continuity: the next explanation uses what happened before.

## 02:20-02:40 | PARA QUIÉN Y CTA

**Pantalla, no leer:** Cerrar en dashboard. Rótulo final: SCHOOL COMMUNITY MEMORY. Try the public demo. Mostrar enlace público: https://mwn2zjxcm2sz7jtrpj3y6ttblq0svgru.lambda-url.us-east-1.on.aws/judge/memory/ Código: REPASO-LIVE. Indicar en pantalla: Self-service demo: synthetic rehearsal. El video anterior muestra registros reales de AWS; mantener esa distinción.

Our Good Neighbor proposal supports community facilitators and families between meetings, starting with fourth-grade mathematics.

A human can follow the evidence, understand what was tried, and choose the next step.

Try the public demo. Repaso keeps the conversation connected to what comes next.

## Sources and claim boundaries

[UNICEF end-2025 Venezuela report](https://www.unicef.org/media/178481/file/Venezuela-Humanitarian-SitRep-No.2-(End-of-Year),-31-December-2025.pdf.pdf), published January 29, 2026: page 6 supplies the education-need and out-of-school estimates; page 16 supplies the education-response funding requirement and gap. These are humanitarian context figures, not Repaso outcomes or savings.

Strands contributions [#4207](https://github.com/strands-agents/harness-sdk/pull/4207) and [#4208](https://github.com/strands-agents/harness-sdk/pull/4208) were open, not merged, when verified September 14, 2026.

The recorded cake-to-paper explanation change demonstrates memory retrieval and adaptation. Three earlier answers on one repeated question do not establish learning improvement. The community facilitator use case is proposed; the demonstrated access model is family scoped. No partnership or pilot is claimed.
