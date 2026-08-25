# Demo clock — offline escalation-correctness benchmark (2026-08-20)

Thirty simulated students practiced for fourteen simulated days — 420 student-days —
through the real pipeline: the actual Strands graphs, planner, grader, mastery model,
spaced-repetition scheduler, escalation triggers, cohort signal, and item tournament.
What is simulated: the students (deterministic response models with misconception
tables) and the LLM calls (scripted doubles that look answers up in the answer bank).
Everything else — every routing decision, every state transition, every interruption —
is the live system. Wall clock: **14.1 s**. Cost: **$0** (no network, no credentials).

## Setup

| Item | Value |
|---|---|
| Command | `python scripts/run_demo_clock.py --days 14` |
| Seed | 20260901 (same seed → byte-identical transcript) |
| Cohort | 10 steady, 4 struggling, 3 disengaged, 2 fast-guesser, 5 clustered-struggling (one section), 3 forgetting, 2 ambiguous, 1 injector |
| Item bank | 12 grade-4 math competencies × (5 MCQ + 2 open), misconception distractors |
| Escalation gate | mastery level STRUGGLING ∧ attempts ≥ 8 ∧ 7-day cooldown |
| Cohort signal | ≥ 3 distinct families, same section × competency, ≥ 8 attempts each, once per ISO week |
| Grader gate | open answers below confidence 0.85 quarantine — never guessed |
| Settings deviating from defaults | none |

## Volume

420/420 sessions delivered · **1,062 responses graded** · 20 items retired by the
psychometric tournament · 9 struggle triages · 6 engagement alerts (3 students, weekly
cadence) · 1 cohort signal per week · 7 quarantines.

## Outcome vs the planted ledger

| Case | Expected | Actual | Verdict |
|---|---:|---:|---|
| Struggle triage fires for every low-ability student | 9 | 9 | as expected |
| Struggle triage never fires outside the low-ability group | 0 | 0 | as expected |
| Engagement alert reaches every disengaged student | 3 | 3 | as expected |
| Engagement alert never fires for active students | 0 | 0 | as expected |
| Cohort signal fires only for the clustered section | 4-b | 4-b | as expected |
| Cohort signal fires at most once per ISO week | 1–2 | 2 | as expected |
| Injection attempts quarantined before any grading | ≥ 1 | 2 | as expected |
| Hedged open answers quarantined, never auto-graded | ≥ 1 | 5 | as expected |

**The headline number: in 420 student-days the system interrupted a human 17 times —
every one of them planted, zero false interrupts.**

## Bugs found and fixed by this benchmark

| # | Symptom | Fix |
|---|---|---|
| 1 | Disengagement was checked in the response flow — a student who stops responding never generates a response, so the alert could never fire | Engagement sweep moved to the daily-close graph with a weekly claim (`quality_graph.py`) |
| 2 | Ordinary students with an unlucky first day tripped struggle triage when the whole cohort drills the same competency | Escalation minimum-evidence gate raised from 5 to 8 attempts (`settings.py`) |
| 3 | Cohort signal counted STRUGGLING mastery without an evidence guard — fired in every section | Cohort failures now require attempts ≥ the same gate (`quality_graph.py`) |
| 4 | Once the review queue saturated the daily limit, new material starved — high performers never met a single open question | Planner reserves one daily slot for unseen items when any exist (`session_planner.py`) |
| 5 | Simulator: the planted injection had a 10 % chance of silently not firing; three archetypes sat on the struggle boundary | Deterministic injection on days 2–3; abilities recalibrated away from the threshold (`student_sim.py`, `archetypes.py`) |

## Other observations (not fixed)

- The planner's new-material fill is breadth-first across competencies; a per-competency
  depth preference would reach open questions sooner for strong students.
- Cohort weekly re-fire is by design; the pilot will show whether weekly is the right
  cadence for teachers.

## Offline test suite

`pytest -q` → **390 passed** (baseline before this work: 337).

## Honest read

- One seed, one run. The archetypes were designed by the same person who designed the
  triggers — 8/8 proves the machine fires exactly as designed on patterns designed to
  fire it, not that real children behave like the archetypes. The pilot is the only
  external check.
- The LLM calls are scripted doubles: this benchmark validates orchestration, gating,
  and state — not the semantic quality of generated items, feedback, or notes. That is
  the live calibration run (B1/B2), pending only on the account's Bedrock daily-token
  tier materializing.
- Noise variants (±15 % response noise, multiple seeds) are pending; until they run,
  zero-false-interrupts is a single-trajectory result.

## Artifacts left behind

`.local_data/demo_clock/` (git-ignored): full state store, grade log, and outbox of the
run — 420 sessions, 1,062 grades, every outbound message the families would have seen.
