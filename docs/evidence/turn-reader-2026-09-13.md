# The conversational turn, measured — September 13, 2026

322 live Amazon Bedrock calls in `us-east-1`, $0.193457 read from the per-call ledger and
priced from the dated table in `src/repaso/config/pricing.py`. The rows behind every figure
here are in [turn-reader-2026-09-13.json](turn-reader-2026-09-13.json). Nothing was deployed
and no AWS resource was written.

A conversational turn can make two model calls: one that reads what the family's message is,
and one that explains the question when that is what they asked for. Serving a prepared
question and grading a choice make none. This page is about those two calls: which model each
is bound to, what the session window costs when it enters the prompt, and how long the whole
turn takes against the project's sixty-second family-facing gate.

## What the reader is, and what it is not

The reader is one structured call. It receives the question on screen with its options,
whether the family has already answered it, what happened earlier in tonight's practice, the
grade and the topic, and the family's message inside the untrusted frame the ingest screen
already uses. It returns an intent from a closed list, who the message reads as, one line
naming what they want, and — only for an answer — the part of the message that is the answer.
There is no phrase list and no regular expression anywhere in that path: the schema is the
contract.

Only a message the reader calls an answer, while a capsule is open, can reach the grader. So
the number that matters is not the exact intent but the split: answer against not-an-answer.

| Model | exact intent | answer against not | p50 | p95 | $/call |
| --- | --- | --- | --- | --- | --- |
| Nova Micro | 34/44 | 39/44 | 557 ms | 619 ms | $0.000044 |
| Nova Lite | 37/44 | 42/44 | 676 ms | 1,083 ms | $0.000076 |
| Claude Haiku 4.5 | 41/44 | 42/44 | 1,237 ms | 1,678 ms | $0.0019 |

Twenty-two message shapes a family types — a bare option, an option wrapped in a sentence,
"no entiendo", "no entiendo nadaaa 😭", "¿por qué?", "explicame otra vez pf", "otra más", "ya
no quiero, estoy cansado", an exam announcement, "gracias!", a lone 👍 — at two samples each.

Nova Micro is the model the classify role is bound to, and it is the reason the reader is not
bound to that role. Its misses are the expensive kind: in 4 of its 44 calls it filled the
answer field with `6/8`, an option the family never wrote, twice of them on a lone thumbs-up.
The extraction guard accepts a string that names an option, so those would have been graded —
and one of them graded correct. The reader now goes to the structured role, whose default is
Nova Lite and whose deployed binding is Haiku 4.5; both measured 42 of 44 on the split, and
neither invented an answer on a message that was not one.

All three models miss the same two shapes. "sumé uno arriba y abajo" — a method stated aloud,
which is an answer to an open item and reads as an explanation request against a
multiple-choice one — and "repite la pregunta", which every model calls an explanation rather
than a request for the question again. Both misses are safe in the direction that matters:
they refuse to grade, they do not grade the wrong thing.

## What the session window costs

Tonight's window is at most eight turns, each one line: the question, what the family wrote,
the verdict the harness computed, and the label of the approach an explanation used. Measured
on Nova Lite over the same 22 shapes, one sample per arm:

| Remembered turns | input tokens (median) | p50 | $/call |
| --- | --- | --- | --- |
| 0 | 1,122 | 649 ms | $0.0000762 |
| 1 | 1,168 | 654 ms | $0.0000788 |
| 3 | 1,243 | 643 ms | $0.0000832 |

About 40 input tokens a remembered turn, no measurable latency, and a cap of eight notes that
holds the whole evening under +320 tokens whatever the family does.

## Why the explainer is not on the cheapest model

Three situations, two samples on four models: the child asks for help before answering, the
child asks why after choosing a wrong option, and the child says the first explanation did not
land, with the approach that was already tried named in the prompt. Read against five written
rules — Spanish at the grade, at most three short sentences, no answer before the child has
answered, start from what the child wrote, never repeat a way in already tried — scored by
hand by one reader.

| Model | kept the answer back | started from what the child wrote | took a new way in | p50 | $/call |
| --- | --- | --- | --- | --- | --- |
| Nova Micro | 2/2 | 0/2 | 0/2 | 766 ms | $0.000048 |
| Nova Lite | 2/2 | 2/2 | 1/2 | 940 ms | $0.000080 |
| Claude Haiku 4.5 | 2/2 | 2/2 | 2/2 | 2,059 ms | $0.0022 |
| Claude Sonnet 4.6 | 2/2 | 2/2 | 2/2 | 3,315 ms | $0.0067 |

Every model kept the answer back before the child had answered, which is the rule that
protects the measurement. The two cheap models broke the two rules that make the explanation
worth sending: Nova Micro never mentioned the option the child had chosen and repeated the
bar-splitting image it was told had already failed, labelling its own reply with that very
label; Nova Lite addressed the wrong answer but drew the same bars again on one of the two
second tries, and once wrote about the child in the third person to the child, inside an
arithmetic aside that is wrong on its own terms.

So the explainer stays on the generate role, where the default is Sonnet 4.6 and the fallback
is Haiku 4.5 — both of which honoured every rule in this small sample, so the chain degrades
without breaking the design. Sonnet emitted markdown asterisks in 3 of 6 replies and the chat
sends plain text, so the prompt now forbids markup, as the teacher-note prompt already did.

## The clock

The turn that costs the most is a child saying the explanation did not land: read, then
explain. Measured end to end on the default routing, six runs:

| | p50 | p95 |
| --- | --- | --- |
| read | 623 ms | 1,028 ms |
| explain | 2,854 ms | 3,316 ms |
| whole turn | 3,543 ms | 4,343 ms |

$0.006615 a turn, and 4.3 s against a 60 s gate — fourteen times inside it. An answer turn
costs the reader plus what the answer path already spent; a served question and a graded
choice still cost nothing.

## What this does not establish

Not a family result and not an accuracy figure. Twenty-two shapes at two samples is a
conformance run against labels one reader wrote, on one question, in one language, on one day,
and 44 calls is not a rate: the split figures carry no interval worth quoting. The explanation
arms are smaller still, three situations at two samples, scored by the same person who wrote
the rules; no teacher read any of it and no child typed any of it. None of these calls carried
the guardrail the runtime attaches, which the latency work measured at roughly +700 ms a call,
so every latency here is a floor. The deployed runtime also overrides the structured role to
Haiku 4.5, which is measured above and priced 25x the default — the turn is inside the gate
either way, the dollars are not the same.
