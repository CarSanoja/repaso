# Struggle false positives vs simulator ground truth — the essentialism defense fails (2026-08-20)

**Zero of the 32 false-positive struggle interrupts are measurement-correct, and that
kills the excuse.** The seed-sweep report claimed most FPs were "archetype essentialism,
not detector error" (Honest read #2). Scored against the simulator's own deterministic
ability curve, not one FP survives: every flagged student had a true ability of 0.67 or
higher at the moment the system interrupted their family. Ground-truth-adjusted precision
is **0.952 [0.933–0.966]** — identical to the unadjusted number, because the adjustment
credits nothing. All numbers below come from a real 40-seed run of the real pipeline
(scripted model doubles, no network): 16,800 simulated student-days in 132 s, $0.

## Setup

| Item | Value |
|---|---|
| Command | `python scripts/run_seed_sweep.py --seeds 40 --workers 6` then `python scripts/score_fp_ground_truth.py` |
| Runs | 40 held-out seeds (20260902–20260941) × 420 student-days = 16,800 student-days |
| Wall clock / cost | 132 s sweep + 0.2 s scoring / $0 (offline, scripted doubles) |
| Ground truth | `repaso/simulator/student_sim.ability_on_day(PROFILES[archetype], day_index)`, day 0 = 2026-09-01 |
| Criterion | measurement-correct when true ability < 0.50 at fire time (default; swept 0.45/0.50/0.55) |
| Source tree | fingerprint `0d357ec23bfd`; two back-to-back runs produced byte-identical `results.json` |
| Settings deviating from defaults | none |

## What the 663 fires are

| Class | Fires | Share |
|---|---|---|
| Low-ability archetypes (true positives) | 631 | 95.2 % |
| Outside archetypes, measurement-correct | 0 | 0.0 % |
| Outside archetypes, detector noise | 32 | 4.8 % |

Per-fire precision 0.952 [0.933–0.966]. The sweep's per-*student* precision is 0.918
[0.886–0.941] (358 TP students, 32 FP students): the two differ because true positives
refire after the 7-day cooldown (631 fires from 358 students) while **every one of the 32
FP students fired exactly once** — the cooldown is not the problem.

| Archetype | Fires | TP | Measurement-correct | Detector noise |
|---|---|---|---|---|
| cohort_cluster | 345 | 345 | — | — |
| struggling | 286 | 286 | — | — |
| steady_mastery | 13 | 0 | 0 | 13 |
| forgetting | 10 | 0 | 0 | 10 |
| disengaged | 8 | 0 | 0 | 8 |
| ambiguous | 1 | 0 | 0 | 1 |

## Why no criterion rescues them

Ground-truth ability at fire time across the 32 FPs: **min 0.670, median 0.790, max
0.940**. The criterion would have to be raised to 0.68 to credit a single fire and to
0.95 to credit all of them. There is no overlap to exploit — over days 0–13 the two
groups never meet:

| Group | Ability floor | Ability ceiling |
|---|---|---|
| struggling (low) | 0.14 | 0.46 |
| cohort_cluster (low) | 0.17 | 0.51 |
| steady_mastery / injector | 0.65 | 1.00 |
| forgetting | 0.67 | 1.00 |
| disengaged | 0.70 | 1.00 |
| ambiguous | 0.72 | 1.00 |
| fast_guesser | 0.75 | 1.00 |

### Criterion sensitivity

| Criterion | Measurement-correct | Detector noise | Adjusted precision |
|---|---|---|---|
| 0.45 | 0 | 32 | 0.952 [0.933–0.966] |
| 0.50 | 0 | 32 | 0.952 [0.933–0.966] |
| 0.55 | 0 | 32 | 0.952 [0.933–0.966] |

The choice of criterion is not load-bearing anywhere in the band 0.52–0.66.

## What the FPs actually are: a cold-start artifact

Three facts locate the defect precisely.

1. **They fire the instant they are allowed to.** Median attempts at trigger = 8, exactly
   `escalation_min_samples`; range 8–11. All 32 land on day index 2–5, 21 of them on day 2.
2. **They rest on near-coin-flip evidence.** Over the attempts that produced the trigger,
   FP fires averaged 0.426 observed accuracy (13 of 32 at ≥ 0.50, max 0.625). Genuine
   struggle fires averaged 0.266 (34 of 631 at ≥ 0.50). The EMA (α = 0.3, struggling
   ceiling 0.4), seeded from the first outcome, lets three recent wrongs override a
   winning record.
3. **All 32 sit on one competency.** Every FP fired on `math.g4.data.line_plots` — the
   first competency in the grade-4 list, which absorbs 492 of ~1,056 graded attempts per
   seed. It is not harder; it is simply first to reach 8 attempts, so it is where the
   cold-start threshold gets crossed.

Worked case — seed 20260905, `stu09` (steady_mastery, 4-c, true ability 0.79 on day 2),
competency `math.g4.data.line_plots`:

| Attempt | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| Graded | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ |
| EMA | 1.00 | 1.00 | 1.00 | 0.70 | 0.49 | 0.64 | 0.45 | **0.32** |

Five of eight correct — and the family was interrupted on 2026-09-03. The next 13 graded
attempts on that competency were all correct.

## G5 rescored on ground truth

| Measure | Value |
|---|---|
| Cohort signals fired | 86 |
| In `colegio-demo-4-b` (the planted cluster) | 79 |
| Outside `colegio-demo-4-b` | 7 (7 distinct seeds, all `math.g4.data.line_plots`; 6 in 4-c, 1 in 4-a) |
| Outside signals with ≥ 3 distinct families carrying a TP-or-measurement-correct struggle fire in the prior 7 days | **0 / 7** |
| Credited families behind those signals | 1 family × 3 signals, 2 families × 4 signals |
| Signals per section/competency/week | max 1 (weekly throttle holds) |

The out-of-section cohort signals are unjustified, and structurally so: sections 4-a and
4-c contain exactly **two** low-ability students each, below the k = 3 family floor. No
ground-truth-justified cohort signal can exist in those sections at all. The seed-sweep
report's proposed rescue — "scoring cohort on ground truth should recover it" — does not
recover it. G5 is genuine contagion from G2 and will only clear when the struggle
boundary is fixed.

## Honest read

1. **Strike Honest read #2 of the seed sweep.** "Most FPs are archetype essentialism" is
   false at every criterion tested. The defect is real and it is a cold-start defect:
   the detector fires on the eighth attempt of the first competency a student practises,
   before the EMA has the evidence to earn a verdict. The obvious levers — raise
   `escalation_min_samples`, require a minimum attempt count *per competency* before the
   struggling level can escalate, or damp the EMA's first-outcome seeding — are testable
   in one sweep each.
2. **The criterion is a modeling choice, and I picked it before looking.** Here it
   happens not to matter, because the archetype ability bands are disjoint (0.51 vs
   0.65). If the simulator ever gains an archetype whose ability crosses 0.5, this
   scoring becomes criterion-sensitive and the sensitivity table stops being a formality.
3. **`ability_on_day` ignores per-item difficulty.** Items carry difficulty 1–5; the
   ground truth is a single per-day ability with no item term. A capable student
   genuinely defeated by a hard item is invisible to this scoring, and would be scored as
   detector noise. That is the main way these 32 could be less unjust than they look.
4. **Guessing cuts the other way than it usually does.** The simulator does not model
   random guessing on 3-option MCQs — a student who does not know produces the
   misconception distractor unless `guess_probability` fires. Real 3-option MCQs would
   float measured accuracy toward 0.33 for a student answering blind, so real EMAs sit
   higher than simulated ones. Two consequences: the real-world cold-start FP rate is
   probably lower than 4.8 %, and a real EMA below 0.4 on 3-option MCQs implies
   below-chance performance — a stronger claim than this simulation supports.
5. **The G5 proxy understates justification.** The cohort trigger reads mastery states
   directly; my rescoring counts struggle *escalations*, which the cooldown and per-week
   claims throttle. A signal could legitimately stand on three struggling students of
   whom only one escalated. The structural argument (two low-ability students per outside
   section) is what carries the 0/7, not the 7-day window.
6. **A reproducibility bug surfaced and was fixed mid-task.** `run_seed_sweep.py` reused
   its per-seed `local_data` directories; a second run over dirty state silently collapsed
   the gates (injections 0/40, hedged 0/40, fast-guess 0/40) while still printing a clean
   report. `run_one` now clears its seed directory first. Related: my regenerated sweep
   does not reproduce the 2026-08-20 numbers (precision 0.918 vs 0.892, G2 19/40 vs
   16/40, G7 40/40 vs 36/40) because `src/` moved between the two runs. I verified
   determinism instead — two consecutive runs at tree fingerprint `0d357ec23bfd` produced
   byte-identical `results.json`.

## Artifacts

- `.local_data/sweep/results.json` — 40 rows, now carrying `archetypes`, `sections`,
  `struggle_fires` (ISO dates) and `cohort_signals` (`section#competency#date`).
- `scripts/score_fp_ground_truth.py` — the scorer; `--criterion` overrides the default 0.50.
- `tests/benchmarks/test_fp_scoring.py` — 15 unit tests over the classifier and the
  justified-cohort logic.
