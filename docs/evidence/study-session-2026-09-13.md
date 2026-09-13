# The study sitting, walked end to end — September 13, 2026

24 live Amazon Bedrock calls in `us-east-1`, $0.0533 read from the per-call ledger and priced
from the dated table in `src/repaso/config/pricing.py`. The rows behind every figure here are
in [study-session-2026-09-13.json](study-session-2026-09-13.json). Nothing was deployed and no
AWS resource was written; the only calls made were Bedrock inference.

A study sitting is the practice a family asks for on top of the daily capsule. `/sesion`
opens one, `/tema <tema>` opens one on a topic the family names in their own words, `/listo`
closes it, and a plain reply answers the question on screen. This page is what four such
evenings actually did.

## What it is

A resumable state machine with a goal, a budget in questions and minutes, and a clean close.
It serves multiple-choice questions the family's own pages produced, drawn by one store read
and a deterministic sort over what this child can practise on this competency minus what they
have seen. Every answer is keyed by `(sitting, position)`, and the grade log row it writes is
`study:{sitting}:{position}` rather than a fresh id, which is what makes a redelivered message
a replay instead of a second attempt on a child's mastery number.

## What it is not

It is not a second tutor. No number it produces comes from a model: `grade_mcq` is
deterministic, the mastery cell moves through the same `apply_outcome` the capsule uses, and
the attempt ledger records the same shape. It is not an open-answer surface — the judge is not
on this path — and it is not a way around the daily capsule's bounds.

## What a turn costs

| Turn | Model calls | p50 | p95 | slowest observed |
| --- | --- | --- | --- | --- |
| Open a sitting, grade a choice, switch topic, `/status` | 0 | 9 ms | 20 ms | 22 ms |
| Ask for another question, or write with no sitting open | 1 reader | 654 ms | 699 ms | 699 ms |
| Ask for an explanation | 1 reader + 1 explainer | 4,202 ms | 5,095 ms | 5,095 ms |

Eight explanation turns, eight reader-only turns and 24 turns with no model in them, over four
evenings. The project's own gate for a family-facing interaction is p95 under 60 s; the
slowest turn observed is 11.8x inside it. None of these calls carried the Bedrock guardrail
the deployed runtime attaches, which the project's latency work puts at roughly +700 ms a
screened message, so every figure here is a floor.

An evening of ten turns cost $0.013325 over six calls: four to the structured role
(Nova Lite, 651.8 ms p50) and two to the generate role (Claude Sonnet 4.6, 3,323.4 ms p50).
Serving a question and grading a choice cost nothing, which is asserted by a test that the
reader and the explainer are never touched when a message names one of the item's own options.

## An hour of drilling

A simulated hour through the runtime entry point, a bank of 24 questions, `/sesion` re-opened
the moment a sitting closes:

| The evening | Attempts | Episodes | Model calls | What stopped it |
| --- | --- | --- | --- | --- |
| Every answer right, one every 2 min | 6 | 6 | 0 | three questions a sitting, then six a day |
| Every answer wrong, one every 2 min | 3 | 3 | 0 | three wrong in a row, which ends the day |
| Every answer right, one every 4 min | 6 | 6 | 0 | three questions a sitting, then six a day |

What the family is told is "Por hoy ya practicaron bastante, y descansar también es parte de
aprender. Mañana seguimos con lo que costó hoy." No reply on this path names a call count, a
budget, a quota or a limit on the service. The stop is the harness's, and the sentence is
about the child's evening.

## The learning state moves exactly once

| What happens | Attempts | Grade rows | Episodes |
| --- | --- | --- | --- |
| Two messages for one family arrive at once | 1 | 1 | 1 |
| A message older than the question on screen | 0 | 0 | 0 |
| A redelivered webhook mid-sitting | 1 | 1 | 1 |
| The same webhook twice, at once | 1 | 1 | 1 |
| A button from a sitting abandoned between question and answer | 0 | 0 | 0 |

The first row read 2, 2 and 2 before the guard that closed it, and the second of those
attempts was graded against a question that had been served and never delivered to anyone.
The per-family lease does not cover that case: it serialises two turns, it does not stop the
second turn from grading a message composed before the question it now faces. What covers it
is the sitting's own stamp — a message older than the question on screen is not an answer to
it. Telegram dates a message to the second while the sitting serves at the microsecond, so the
same guard refuses a typed answer sent inside the second the question appeared; that is the
width of the false refusal, and the direction it errs in is the right one.

## `/forget` after a sitting

One sitting with an explanation request and one graded answer, then the `forget:yes` callback
through the runtime entry point. Afterwards: zero study rows, zero episode rows, zero
turn-window rows, zero grade rows, no mastery cell, no family, no students, and the sentence
the child typed is not present in any row under the family scope or the chat scope.

## What this does not establish

One synthetic family, one child, one grade, one language, one bank of twelve authored
questions, on one day. Four evenings is not a rate and eight explanation turns are not a
latency distribution. No teacher read any explanation and no child typed any message, so
nothing here says the explanations are good — only that they arrive, that they are pitched at
the grade, that the second one takes a different way in than the first, and that neither
carries the answer to a question the child has not answered. The concurrency, drilling and
erasure rows are deterministic runs over the real code paths with a simulated clock and a
local store: they are not observations of the deployed system, and no deployed table was
written.
