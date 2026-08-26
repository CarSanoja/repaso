# Pre-registered gates — multi-seed escalation sweep

Committed **before** any sweep run, per the adversarial review (F-02, F-03). The
calibration seed **20260901** was used to tune thresholds and simulator profiles; it is
therefore **in-sample and excluded**. The sweep runs 40 held-out seeds, 20260902–20260941,
14 days × 30 students each, via `scripts/run_seed_sweep.py`.

## Gates (pass/fail declared in advance)

| # | Gate | Threshold |
|---|---|---|
| G1 | Struggle recall: all 9 low-ability students reached | in ≥ 95 % of seeds |
| G2 | Struggle false-positive students = 0 | in ≥ 95 % of seeds; full distribution reported |
| G3 | Every refire gap ≥ 7 days | 100 % of refires, all seeds |
| G4 | Engagement: exactly the 3 disengaged students | in ≥ 90 % of seeds |
| G5 | Cohort signal: only section 4-b, ≤ 1 per ISO week | sections in ≥ 95 %; weekly cap in 100 % |
| G6 | Injections intercepted = injections planted | all seeds |
| G7 | Hedged opens quarantined = hedged planted | all seeds |
| G8 | Fast-guess switch = exactly the 2 fast guessers | in ≥ 90 % of seeds |

## Metrics reported regardless of outcome

- Pooled struggle-interrupt **precision and recall with Wilson 95 % CIs** across all
  seeds (TP = fired∩low-ability, FP = fired outside).
- Distribution of total human interruptions per run (p50/p95).
- **Baselines**: never-interrupt (recall 0 by construction) and a rate-matched random
  interrupter (k interrupts uniformly over 30 students; expected precision 9/30 = 0.30).
- Failures are reported as failures. This file does not change after runs; deviations
  get a new dated report.
