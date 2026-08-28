# Dev log — Benchmark 002: the adversarial round

**Date:** 2026-08-20
**Domain:** Benchmark
**Fulfills:** the ML adversarial review's first-five actions (docs/product/benchmark-suite.md)
**Verification:** offline suite **675 passed**; ruff clean; every claim below has a dated
report under `docs/reports/`.

## The arc

An external-reviewer critique (17 findings, 6 critical) was commissioned against the
first benchmark and executed the same day, largely by parallel agent workflows:

1. **Three shipped defects fixed and generalized 40/40**: the Armor spoke no Spanish;
   the documented cooldown did not exist (now per student, exercised by a
   parent-resolution simulator); the fast-guess detector was structurally dead (now a
   20-response latency window).
2. **The fixture-oracle ledger was replaced by falsifiable rows**, gates were
   pre-registered in git before any run, and a 40-seed held-out sweep failed two of
   them honestly — killing the single-seed "zero false interrupts" claim.
3. **G7's misses exposed an instrument defect** (a stranded scripted-judge prime
   silently corrupting ten seeds); fixed with per-answer settling and a tripwire, with
   fix-off/fix-on attribution.
4. **Ground-truth scoring falsified our own first interpretation**: zero of the false
   positives were struggling students — they were a day-2-5 cold-start artifact on the
   EMA estimator.
5. **Sensitivity curves + a 2-D interaction slab** located `min_samples = 8` one notch
   below its plateau; the gate moved to 9 on disjoint-seed evidence and was validated
   on forty virgin seeds: **precision 0.892 → 0.970 [0.947–0.983], recall 0.994,
   7 of 8 pre-registered gates passing**.
6. **The Armor corpus** (400 bilingual attacks, 9 families, OCR corruption): 400/400
   intercepted, 0 % false-block; PII is now redacted before the grading model call.
7. **The school calendar**: masking silence by scheduled days took calendar-caused
   false disengagement alerts to zero per 100 student-weeks with dropout detection at
   3 school days — proven with an on/off/flat three-arm bench whose control arm fails
   by design.

## Standing reds, on the board deliberately

- G2: 11 residual struggle FPs across 40 virgin seeds (below its 95 % bar); next step
  is ground-truth scoring of the residue.
- Outage-shaped silence needs a delivery-health precondition before the engagement
  sweep — a cohort-wide response collapse is trivially detectable and nothing checks it.
- Recall under a 5-day school week is under-audited: earlier recall figures assumed
  daily practice; with 13 practice days per 28 calendar days the evidence gate takes
  two calendar weeks to fill.
- Daily-close delivery still lands on rest days (the verdict is fixed, the delivery
  moment is not), and the engagement copy now counts school days — a semantics change
  pending sign-off.

## Also landed

/exam with real dates and pre-exam planning, /status with real aggregates, the
scripts/ case-matrix README, node-and-LLM telemetry with a command-center stream, and
seed-hygiene bookkeeping (calibration/gate/sensitivity/validation ranges disjoint).
