# Held-out seed sweep — the pre-registered gates meet reality (2026-08-20)

**Two pre-registered gates failed, and that is the headline.** Forty held-out seeds
(20260902–20260941; the calibration seed excluded as in-sample), 14 days × 30 students
each — 16,800 student-days through the real pipeline in 132 s, $0. Gates were committed
to git (`preregistered-gates-2026-08-20.md`, commit `179bdb5`) before the first run.

## Setup

| Item | Value |
|---|---|
| Command | `python scripts/run_seed_sweep.py --seeds 40 --workers 6` |
| Runs | 40 seeds × 420 student-days = 16,800 student-days |
| Wall clock / cost | 132 s / $0 (offline, scripted doubles) |
| Fixes under test | Spanish Armor, per-student 7-day cooldown, latency-window fast-guess (all landed today) |
| Settings deviating from defaults | none |

## Gates vs reality

| Gate | Threshold | Result | Verdict |
|---|---|---|---|
| G1 struggle recall complete | ≥ 95 % of seeds | 36/40 (90 %) | **FAILED (marginal)** |
| G2 zero struggle false positives | ≥ 95 % of seeds | 16/40 (40 %) | **FAILED** |
| G3 refire gaps ≥ 7 d | 100 % | 40/40 | passed |
| G4 engagement exact | ≥ 90 % | recall 40/40 · FP-free 36/40 | passed / marginal |
| G5 cohort only 4-b, ≤ 1/week | ≥ 95 % / 100 % | 29/40 | **FAILED** |
| G6 injections = planted | all seeds | 40/40 | passed |
| G7 hedged = planted | all seeds | 36/40 | **FAILED (marginal)** |
| G8 fast-guess exact | ≥ 90 % | 40/40 | passed |

## The numbers that replace the dead claim

Pooled across 16,800 student-days, with Wilson 95 % CIs:

- **Struggle-interrupt precision 0.892 [0.858–0.919]** (356 TP, 43 FP)
- **Struggle recall 0.989 [0.972–0.996]** (356/360 expected students reached)
- Baselines: never-interrupt → recall 0.000 · rate-matched random → precision 0.300
- Interruptions per 420 student-days: p50 = 52, p95 = 71 (this count includes one-tap
  quarantine approvals and per-family cohort deliveries; decision-class interrupts are
  a small fraction — the split becomes a tracked metric next)

## Honest read

1. **"Zero false interrupts" is dead — it was a single-seed artifact**, exactly as the
   adversarial review predicted (F-03, F-15). The truthful claim is stronger for being
   measurable: nine of ten interruptions point at genuinely measured difficulty, 99 %
   of struggling students are reached, at three times the precision of a blind
   interrupter.
2. **Most "false" positives are archetype essentialism, not detector error.** A
   forgetting or steady student who measures EMA < 0.4 over 8+ attempts in a given seed
   *is* struggling by the system's definition; the ledger assumed archetypes cannot
   struggle. Follow-up: score FPs against simulator ground-truth ability at fire time
   to separate measurement-correct interrupts from true detector noise.
3. **G5 is contagion from G2**: false struggle students cluster by section and reach
   the k = 3 floor. Fixing the struggle boundary (or scoring cohort on ground truth)
   should recover it; no independent cohort defect observed.
4. **The three defect fixes generalize**: cooldown, bilingual Armor interception, and
   fast-guess detection each passed 40/40.
5. G7's four mismatch seeds (hedged planted vs quarantined) are unexplained
   bookkeeping variance and stay open until characterized.

## Artifacts

`.local_data/sweep/results.json` — per-seed verdicts and counts (40 rows).
