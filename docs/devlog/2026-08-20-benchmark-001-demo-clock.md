# Dev log — Benchmark 001: the demo clock earns its keep

**Date:** 2026-08-20
**Domain:** Benchmark
**Fulfills:** Plan 001 (escalation-correctness benchmark, offline layer)
**Verification:** offline suite **390 passed**; full report in
[`docs/reports/demo-clock-offline-2026-08-20.md`](../reports/demo-clock-offline-2026-08-20.md).

## Result

Thirty simulated students, fourteen simulated days, the real pipeline end-to-end:
**420 student-days, 1,062 graded responses, 17 human interruptions — all planted, zero
false — in 14.1 s at $0.** Eight of eight planted-ledger cases `as expected`.

## The benchmark found five real defects before any family could

1. Disengagement detection lived in the response flow — a student who stops responding
   never generates a response, so the alert could never fire. Moved to the daily close.
2. The escalation evidence gate (5 attempts) tripped on ordinary students with an
   unlucky first day; raised to 8.
3. The cohort signal counted STRUGGLING mastery without an evidence guard and fired in
   every section; now requires the same gate.
4. The planner starved new material once review debt saturated the daily limit — high
   performers never met a single open question. One daily slot is now reserved for
   unseen items.
5. Simulator calibration: the planted injection had a 10 % silent-miss chance; three
   archetypes sat on the struggle boundary.

## Honest read (carried forward)

Single seed; archetypes designed by the trigger designer; scripted doubles validate
orchestration and gating, not semantic quality. The live calibration runs (item
quality, grading agreement, latency/cost) are staged and wait only on the Bedrock
daily-token tier. An external ML-research adversarial review of these limits was
commissioned the same day.
