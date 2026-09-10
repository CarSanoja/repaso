# Development-split answer evaluation — September 12, 2026

Thirty synthetic fourth-grade fraction answers, the development half of the sixty in
`evaluation/answer_review_set.jsonl`, graded by the repository's judge role against real
inference. Every number below compares the grader with **author-proposed labels**. The
protocol says those labels are not independent teacher judgements and no teacher has completed
any, so this is agreement with the person who wrote the answers, never accuracy against ground
truth. The held-out half was not opened.

All figures come from [the artifact](answer-evaluation-development-2026-09-12.json), which is
built from the collected batches by `scripts/report_answer_evaluation.py`. Raw batches, their
call ledgers and their telemetry stay out of the repository.

## What was run

| | |
| --- | --- |
| Model | `us.anthropic.claude-sonnet-4-6`, judge role, prompt `v1` |
| Region and day | us-east-1, September 12, 2026, 07:51–07:53 UTC |
| Cases | 30 development cases, collected in three bounded batches over disjoint slices |
| Calls | 25 live structured calls; 5 answers never reached a model |
| Failures | 0 provider errors, 0 schema rejections, 0 calls without reported usage |
| Cost | $0.1465, read from the per-call ledger: 28,380 input and 4,089 output tokens priced from the dated table |
| Latency | 2,602.6 ms median, 3,921.4 ms at the 95th percentile |

The five answers with no call are the injection category: the local screener refused them before
any model saw them. That is a rule outcome, not a model judgement, and they are counted as
held-for-review in every denominator below.

## Denominators, including the uncomfortable one

Thirty cases are thirty question-and-answer pairs, not thirty independent answers. The
development half draws on **five distinct questions** and **eighteen distinct answer texts**.
Three of the six categories repeat one answer across all five question groups:

| Category | Cases | Distinct answers |
| --- | --- | --- |
| clear_correct | 5 | 5 |
| correct_conclusion_wrong_reason | 5 | 1 |
| partial | 5 | 5 |
| ambiguous | 5 | 1 |
| informal_correct | 5 | 5 |
| injection | 5 | 1 |

A per-category result of 5/5 in `ambiguous`, `injection` or `correct_conclusion_wrong_reason` is
one answer text seen five times against five different questions. It is not five independent
observations, and nothing here should be read as a rate.

## Result at the product threshold, 0.85

| Measure | Value | Denominator |
| --- | --- | --- |
| Automatic decisions | 22 | 30 cases (coverage 0.733) |
| Held for a person | 8 | 5 screened, 3 below the threshold |
| Grade agreement on automatic decisions | 1.000 | 18 automatic decisions with a boolean author grade |
| Grade agreement on every graded comparison | 1.000 | 20 cases the author graded, held-back ones included |
| Review-decision agreement | 0.800 | 30 cases |
| Automatic decisions called correct | 8 | of 18 |
| False automatic-correct | 0 | of 8 called correct |
| False automatic-correct rate | 0.000 | Wilson 95%: **0.000 – 0.324** |

Ten of the thirty cases — the ambiguous and injection categories — carry no author grade, only
`needs_review: true`. They are counted in the review-decision comparison, where the author's
judgement is complete, and left out of grade agreement, which is reported over its own
denominator of twenty.

Zero false automatic-correct decisions out of eight is not a low rate. The interval it supports
reaches 32.4%. About seventy-four automatic correct decisions with no false one would be needed
to put that bound under 5%.

### By category, at 0.85

| Category | Cases | Automatic | Grade agreement | Review agreement |
| --- | --- | --- | --- | --- |
| clear_correct | 5 | 5 | 1.000 (5) | 1.000 |
| correct_conclusion_wrong_reason | 5 | 5 | 1.000 (5) | 1.000 |
| partial | 5 | 5 | 1.000 (5) | 1.000 |
| informal_correct | 5 | 3 | 1.000 (3) | 0.600 |
| ambiguous | 5 | 4 | no author grade | 0.200 |
| injection | 5 | 0 | no author grade | 1.000 |

The grader never agreed with a wrong conclusion: it called all five wrong-reason answers
incorrect and all five partial answers incorrect, matching the author. The two categories it
disagrees with the author about are the ones where nothing is being graded and everything is
being decided: whether a person should look.

## What the threshold buys and costs

The sweep runs 0.70 to 1.00 in steps of 0.01 on the development split only. Nothing changes
between breakpoints because the grader reports few distinct confidences: 0.82 three times, 0.85
eight times, 0.90 twice, 0.92 three times, 0.95 four times, 0.97 five times.

| Threshold | Automatic | Coverage | Review agreement | Graded decisions | Grade agreement | Called correct | False automatic-correct | Wilson 95% upper |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.70 – 0.82 | 25 | 0.833 | 0.833 | 20 | 1.000 | 10 | 0 | 0.278 |
| 0.83 – 0.85 | 22 | 0.733 | 0.800 | 18 | 1.000 | 8 | 0 | 0.324 |
| 0.86 – 0.90 | 14 | 0.467 | 0.800 | 14 | 1.000 | 5 | 0 | 0.434 |
| 0.91 – 0.92 | 12 | 0.400 | 0.733 | 12 | 1.000 | 5 | 0 | 0.434 |
| 0.93 – 0.95 | 9 | 0.300 | 0.633 | 9 | 1.000 | 5 | 0 | 0.434 |
| 0.96 – 0.97 | 5 | 0.167 | 0.500 | 5 | 1.000 | 5 | 0 | 0.434 |
| 0.98 – 1.00 | 0 | 0.000 | 0.333 | 0 | none | 0 | 0 | none |

Two things this table says plainly. The error the gate exists to prevent was never observed at
any threshold, so the sweep cannot rank candidates by it; raising the threshold only shrinks the
denominator and widens the interval. And 0.85 sits exactly on a mass point: eight of the
twenty-five calls reported 0.85, so the product rule admits them by a hair. A model that
reported 0.84 for the same answers would cut coverage from 0.733 to 0.467 without behaving any
differently.

## The threshold, frozen

**The threshold stays at 0.85.** It is frozen here, on the development split, before the
held-out half is opened, for prompt `v1` and model `us.anthropic.claude-sonnet-4-6`.

The criterion: move the threshold only for a measured reduction in the error it exists to
prevent — a decision called correct automatically that a label says is wrong — and break ties
against moving a rule the rest of the system already depends on.

Applied: false automatic-correct is zero at every point in the sweep, so no candidate is
measurably better on that axis. Review-decision agreement never improves above 0.85, and below
it improves by a single case out of thirty (25/30 at 0.82 against 24/30 at 0.85) — within the
noise of a split whose ambiguous category is one answer text repeated five times, and bought by
lowering the gate under every confidence this model produced, which would make the gate inert.
Coverage falls monotonically as the threshold rises and buys nothing measurable. So 0.85 stands,
and it stands unchanged as a product rule, not as a calibrated probability.

What would justify revisiting it: independent teacher labels, particularly on the ambiguous
band; enough automatic correct decisions to bound the false rate meaningfully; and a fresh sweep
whenever the prompt version or model id changes, because this one is fitted to confidences that
model produced on that day.

## The six disagreements, verbatim

All six are review-decision disagreements. There were no grade disagreements among the
automatic decisions.

Four ambiguous answers were decided without a person. The grader called each one not correct at
exactly 0.85 confidence and awarded 1 of 2 rubric points; the author label says a person should
have looked:

> **eval-01-ambiguous** — Q: *Explica por qué 1/2 y 2/4 son equivalentes.* — A: *Creo que sí porque las dos se parecen.*
> model: correct `false`, confidence 0.85, rubric 1.0, decided automatically. Author: grade unknown, needs review.

The same answer text, decided the same way, against the questions in groups 02, 03 and 04
(`eval-02-ambiguous`, `eval-03-ambiguous`, `eval-04-ambiguous`). In group 05 the same answer
drew 0.82 and was held for a person, which is the behaviour the label asks for.

Two informal but correct answers were held back when the author says no review was needed:

> **eval-03-informal_correct** — Q: *Explica por qué 3/4 y 6/8 son equivalentes.* — A: *Hice 2 pedacitos de cada parte: ahora hay 8 partes y 6 pintadas, la misma cantidad de antes.*
> model: correct `true`, confidence 0.82, rubric 2.0, held for review. Author: correct, no review needed.

> **eval-05-informal_correct** — Q: *Explica por qué 2/5 y 4/10 son equivalentes.* — A: *Hice 2 pedacitos de cada parte: ahora hay 10 partes y 4 pintadas, la misma cantidad de antes.*
> model: correct `true`, confidence 0.82, rubric 2.0, held for review. Author: correct, no review needed.

The costly half of that list is the first. Deciding an ambiguous answer automatically means a
child is told their explanation is incomplete with no adult in the loop, and the confidence the
grader reported for those four is indistinguishable from the confidence it reported for answers
it judged correctly.

## What this does not establish

- Not accuracy. Author labels are proposals by the person who wrote the answers. No independent
  teacher has labelled any case; the scorer refuses to mark a quality claim as allowed on these
  labels, and does so in the artifact.
- Not a rate. Thirty cases, eighteen distinct answers, five distinct questions, one competency,
  one language, one day, one model, one prompt version. Three categories rest on a single
  answer text each.
- Not a false-automatic-correct rate. Zero observed in eight decisions bounds the rate at 32.4%,
  which is not a safety result.
- Not held-out evidence. The thirty held-out cases were not collected or scored.
- Not injection robustness. Those five answers were stopped by a local rule before any model
  call. This says nothing about whether the grader would have resisted them.
- Not a calibration. The grader's confidence is self-reported, takes six distinct values here,
  and separates the answers a person should see from the rest only at the margin: the ambiguous
  answers and the correctly graded informal ones sit in the same 0.82–0.85 band.
