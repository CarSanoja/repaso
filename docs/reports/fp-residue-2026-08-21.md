# The G2 residue — the same cold-start defect, one attempt later (2026-08-21)

**The eleven false positives that survived `escalation_min_samples = 9` are not a second
mechanism. They are the same cold-start failure the 2026-08-20 autopsy described, shifted by
exactly the size of the parameter change.** Every one of them fires on the same competency, in
the same three-day window, at the new attempt floor, on a student whose latent ability is 0.75
or higher — and, as before, not one is measurement-correct at any criterion tested. What the
parameter bought is real: 32 false-positive students became 11 and per-fire precision went
0.952 → 0.982. What it did not buy is a different failure. All numbers below come from a real
40-seed run of the real pipeline on virgin seeds (scripted model doubles, no network): 16,800
simulated student-days in 227 s, plus 0.18 s of scoring, $0.

## Setup

| Item | Value |
|---|---|
| Command | `nice -n 19 ./.venv/bin/python scripts/run_seed_sweep.py --seeds 40 --first-seed 20261000 --workers 3 --base-dir .local_data/validation --out .local_data/validation/results.json` then `nice -n 19 ./.venv/bin/python scripts/score_fp_ground_truth.py --results .local_data/validation/results.json --residue-dir .local_data/validation` |
| Runs | 40 seeds (20261000–20261039) × 14 days × 30 students = 16,800 student-days |
| Wall clock / cost | 227 s sweep (3 workers, `nice -n 19`) + 0.18 s scoring / $0 — offline, scripted doubles |
| Ground truth | `simulator/student_sim.ability_on_day(PROFILES[archetype], day_index)`, day 0 = 2026-09-01 |
| Criterion | measurement-correct when latent ability < 0.50 at fire time; swept 0.45 / 0.50 / 0.55 |
| Residue evidence | per-fire competency from `state/escalations.json`, attempts and observed accuracy replayed from `state/grades.jsonl` up to and including the fire date |
| Settings deviating from defaults | none. `escalation_min_samples = 9` is the tree's current default |
| Source tree | struggle path unchanged for the whole task — `response_graph.py`, `escalation_triggers.py`, `mastery.py`, `adaptation_policy.py`, `demo_clock.py`, `student_sim.py`, `archetypes.py` all last written 2026-08-20 23:09 or earlier. A concurrent change to the daily close (`quality_graph.py`, `calendar.py`) landed four minutes *after* this sweep finished; see Honest read 8 |

### What was declared before the run

Nothing in this pass is a fresh threshold. The classifier, the 0.50 criterion and the
0.45 / 0.50 / 0.55 sweep are inherited unchanged from
`docs/reports/fp-groundtruth-2026-08-20.md`, published yesterday, and so is the signature the
residue is tested against — **day index 2–5, first competency of the grade-4 list, attempts at
the `escalation_min_samples` floor, near-coin-flip observed accuracy, latent ability ≥ 0.65,
exactly one fire per false-positive student**. Five of those six facts are stated as numbers in
that report, so "same mechanism or a new one" is decidable against a frozen comparison rather
than against a story written after the table.

The seeds are the calibration report's virgin range, spent once on that validation and now read
a second time. **Nothing here was tuned on them** — no parameter moved in this pass, and the
guard proposed at the end is deliberately left unmeasured, with its own fresh range named.

## The sweep reproduces the calibration run exactly

| Gate | Bar | Calibration report (2026-08-20) | This run |
|---|---|---|---|
| G1 recall complete | ≥ 95 % | 38/40 | 38/40 |
| G2 zero FP students | ≥ 95 % | 30/40 | **30/40** |
| G3 cooldown gaps | 100 % | 40/40 | 40/40 |
| G4 engagement | ≥ 90 % | 36/40 | 36/40 |
| G5 cohort clean | ≥ 95 % | 38/40 | 38/40 |
| G6 injections | 100 % | 40/40 | 40/40 |
| G7 hedged strict | 100 % | 40/40 | 40/40 |
| G8 fast-guess | ≥ 90 % | 40/40 | 40/40 |

Pooled: precision 0.970 [0.947–0.983] (tp 358, fp 11), recall 0.994 [0.980–0.998] (expected
360), interrupts per 420 student-days p50 53 / p95 63. Every figure matches the calibration
report digit for digit, on a machine and a day it did not run on — the run is reproducible, and
the eleven students it is about are the same eleven.

## What the 605 fires are

| Class | Fires | Share |
|---|---|---|
| Low-ability archetypes (true positives) | 594 | 98.2 % |
| Outside archetypes, measurement-correct | 0 | 0.0 % |
| Outside archetypes, detector noise | 11 | 1.8 % |

Per-fire precision 0.982 [0.968–0.990]; ground-truth-adjusted precision is identical, because
the adjustment again credits nothing.

| Archetype | Fires | TP | Measurement-correct | Detector noise |
|---|---|---|---|---|
| cohort_cluster | 328 | 328 | — | — |
| struggling | 266 | 266 | — | — |
| disengaged | 6 | 0 | 0 | 6 |
| steady_mastery | 4 | 0 | 0 | 4 |
| forgetting | 1 | 0 | 0 | 1 |

### Criterion sensitivity

| Criterion | Measurement-correct | Detector noise | Adjusted precision |
|---|---|---|---|
| 0.45 | 0 | 11 | 0.982 [0.968–0.990] |
| 0.50 | 0 | 11 | 0.982 [0.968–0.990] |
| 0.55 | 0 | 11 | 0.982 [0.968–0.990] |

The criterion is even less load-bearing than last time. The lowest latent ability behind any of
the eleven is **0.750**, so no criterion below 0.751 credits a single fire — against 0.68 for
the 32 fires at `min_samples = 8`. Raising the floor did not remove the *least* unjust fires
first; it removed the earliest ones, and the survivors sit further from the boundary.

## The eleven, one row each

| Seed | Student | Archetype | Section | Day index | Attempts | Observed accuracy | Latent ability |
|---|---|---|---|---|---|---|---|
| 20261003 | stu15 | disengaged | 4-c | 2 | 9 | 0.222 | 0.750 |
| 20261029 | stu17 | disengaged | 4-c | 2 | 9 | 0.333 | 0.750 |
| 20261028 | stu17 | disengaged | 4-c | 3 | 9 | 0.444 | 0.850 |
| 20261033 | stu04 | steady_mastery | 4-a | 3 | 10 | 0.500 | 0.890 |
| 20261038 | stu17 | disengaged | 4-c | 3 | 10 | 0.500 | 0.850 |
| 20261022 | stu02 | steady_mastery | 4-a | 3 | 11 | 0.545 | 0.890 |
| 20261025 | stu07 | steady_mastery | 4-c | 3 | 11 | 0.545 | 0.890 |
| 20261020 | stu04 | steady_mastery | 4-a | 3 | 12 | 0.333 | 0.890 |
| 20261026 | stu27 | forgetting | 4-c | 4 | 9 | 0.556 | 0.940 |
| 20261033 | stu15 | disengaged | 4-c | 4 | 9 | 0.556 | 0.900 |
| 20261018 | stu16 | disengaged | 4-a | 4 | 10 | 0.500 | 0.900 |

Every one of the eleven fired on `math.g4.data.line_plots`, and eleven fires come from eleven
distinct students — no false positive refires. Ten distinct seeds carry them (20261033 carries
two), which is exactly the 30/40 that G2 reports.

## Same signature, or a new one?

Both columns below are produced by the **same scorer on the same artifacts**, not quoted across
reports: `.local_data/sweep/` still holds the 40 backends of the `min_samples = 8` run, so
`score_fp_ground_truth.py --results .local_data/sweep/results.json --residue-dir
.local_data/sweep` re-derives its 32 rows by exactly the method used on the 11.

| Signature fact | `min_samples = 8` (seeds 20260902–41) | `min_samples = 9` (this run, seeds 20261000–39) |
|---|---|---|
| Detector-noise fires | 32 | **11** |
| Distinct FP students | 32 | 11 |
| Fires per FP student | 1 | 1 |
| Distinct seeds carrying them | 21 → G2 19/40 | 10 → G2 30/40 |
| Competency | 100 % `math.g4.data.line_plots` | **100 % `math.g4.data.line_plots`** |
| Day index | 2 : 21 · 3 : 9 · 4 : 1 · 5 : 1 | **2 : 2 · 3 : 6 · 4 : 3** |
| Attempts at trigger (upper bound) | 8 : 18 · 9 : 7 · 10 : 4 · 11 : 3, median 8 | 9 : 5 · 10 : 3 · 11 : 2 · 12 : 1, median 10 |
| Sitting exactly on the floor | 18 of 32 at 8 | 5 of 11 at 9 |
| Cumulative accuracy | mean 0.443, median 0.444, range 0.333–0.625 | mean 0.458, median 0.500, range 0.222–0.556 |
| Latent ability | min 0.670 / median 0.790 / max 0.940 | min 0.750 / median 0.890 / max 0.940 |
| Archetypes | steady 13 · forgetting 10 · disengaged 8 · ambiguous 1 | disengaged 6 · steady 4 · forgetting 1 |
| Measurement-correct at any criterion | 0 | 0 |

The seed counts are their own check: 40 − 21 = 19 and 40 − 10 = 30 are exactly the G2 values the
calibration report published for those two configurations, arrived at from the other direction.

**This is the same defect one notch to the right.** Six of six frozen signature facts survive:
one competency, the first days of the run, the attempt floor, coin-flip evidence, high latent
ability, one fire per student. The distributions shifted by about the size of the parameter
change and by nothing else.

The mechanism is exact, and it needs no simulation to see. Mastery is an EMA with α = 0.3, so
three consecutive wrong answers multiply it by 0.7³ = **0.343**. That is below
`STRUGGLING_CEILING = 0.40` *from any prior value at all*, including a perfect 1.00; from a
prior below 0.816 two wrong answers are enough. `struggle_trigger` then asks only two further
questions — are there `min_samples` attempts, and is the cooldown spent. **`escalation_min_samples`
does not gate the evidence, it gates the calendar**: it decides the earliest attempt at which a
three-wrong run is allowed to page a parent, not whether the run means anything. Moving it 8 → 9
bought one attempt of delay, which is why two thirds of the fires disappeared and the survivors
look identical.

Two secondary observations, both weaker than the above:

1. **The residue shifted toward the students who answer most.** Under a null where false
   positives fall on non-low-ability students in proportion to their number, the expected count
   for `disengaged` is 11 × 120/840 = 1.57; six landed there. Poisson gives P(X ≥ 6) ≈ 0.006.
   `disengaged` is the only non-low-ability archetype with `response_rate = 1.00` (the rest are
   0.95), so it reaches any attempt floor first — and note it does this *before* its
   `dropout_day = 6`, so these are alerts about children who were, at that moment, the most
   diligent responders in the cohort. Per-population rates: disengaged 6/120 = 5.0 %,
   steady_mastery 4/400 = 1.0 %, forgetting 1/120 = 0.8 %, ambiguous 0/80, fast_guesser 0/80,
   injector 0/40.
2. **`forgetting` stopped being the leader.** At `min_samples = 8` it carried 10 of 32
   (8.3 % of its student-runs); here it carries 1 of 11 (0.8 %). Its 0.15 third-day dip needs
   the trigger to be armed on exactly the wrong day, and one more required attempt is often
   enough to step past it. With eleven events this is an observation, not a finding.

## G5 rescored on ground truth

| Measure | 2026-08-20 (`min_samples = 8`) | This run |
|---|---|---|
| Cohort signals fired | 86 | 77 |
| In `colegio-demo-4-b` (the planted cluster) | 79 | 75 |
| Outside `colegio-demo-4-b` | 7 | **2** |
| Outside signals with ≥ 3 credited families in the prior 7 days | 0 / 7 | **0 / 2** |
| Credited families behind those signals | 1 × 3, 2 × 4 | 2 × 2 |

G5 now passes its gate (38/40) while remaining, on ground truth, entirely unjustified where it
fires outside the cluster: both stray signals stand on two credited families, and sections 4-a
and 4-c hold exactly two low-ability students each — below `cohort_min_families = 3`. The gate
passing and the signal being justified are still two different claims, and only the first is
true. G5 shrank because G2 shrank, exactly as the earlier report predicted it would.

## A guard worth measuring — proposed, not implemented, not tuned

**Corroboration floor.** Escalate struggle only when the recency-weighted EMA is below
`STRUGGLING_CEILING` *and* the plain cumulative accuracy on that competency
(`state.correct / state.attempts`) is also below `STRUGGLING_CEILING`. Both numbers already
live on `MasteryState`; no new constant is introduced, and the second test is the one thing the
first cannot do — ask whether the child's record, not just its tail, looks like struggle.

Predicted effect, by arithmetic on the printed rows — and, usefully, on two disjoint seed ranges,
because the same scorer re-derives the `min_samples = 8` residue:

| Quantity | `min_samples = 9`, now | Predicted with the floor | `min_samples = 8` residue, same floor |
|---|---|---|---|
| Detector-noise fires | 11 | **3** (only 0.222, 0.333, 0.333 survive) | 32 → 12 |
| Seeds failing G2 | 10 | 3 → G2 **37/40** | 21 → 8 → G2 32/40 |
| Per-fire precision | 0.982 | ≈ 0.995 | 0.952 → ≈ 0.981 |

The floor removes 8 of 11 fires on one seed range and 20 of 32 on a disjoint one — the same
two-thirds cut, twice, which is what a mechanism-level fix should look like and what a fit to
eleven points would not.

Predicted cost, from the simulator's own profiles rather than from any fit. A student answers
correctly with probability `ability + (1 − ability)·guess_probability`: a `struggling` child at
day index 3 has ability 0.26 and `guess_probability` 0.10, so p = 0.334, and with nine attempts
P(cumulative accuracy ≥ 0.40) = P(X ≥ 4 | X ~ Bin(9, 0.334)) = **0.35**; a `cohort_cluster` child
at day index 4 has p = 0.397 and the same calculation gives **0.51**. **Roughly four in ten genuine first-opportunity fires would be deferred by at
least one attempt.** On a 14-day daily-practice sweep that is a latency cost and almost
certainly not a recall cost. On a five-day school week it may be neither: the companion audit
(`docs/reports/school-week-recall-2026-08-21.md`) shows the detection window closing after about
nine school days, and a deferral inside a closing window can cost recall outright.

**Falsification, declared here so it cannot be chosen later.** Implement the floor, then run
`run_seed_sweep.py` *and* `run_school_week_audit.py` on seeds **20261300–20261339** (fresh; the
hygiene table's ranges through 20261219 are spent). Accept only if all three hold: G2 ≥ 38/40,
school-week struggle recall ≥ 0.95, median school-week detection latency ≤ 6 scheduled days.
Any one failing kills it.

Two alternates, both cheaper to reason about and both worse:

- **A day-spread floor** — require attempts on at least *k* distinct scheduled days before the
  competency can escalate. All eleven fires sit at day index 2–4, so k = 4 would remove eight
  of them; it would also delay every genuine detection by the same amount, and the audit's p50
  is already 4 scheduled days.
- **A persistence check** — require the mastery level to read STRUGGLING at two consecutive
  daily closes. This attacks the tail directly, costs one day of latency on every true
  positive, and does nothing about a child whose last six answers were wrong for a fortnight.

Neither touches the root cause, which is that the EMA is seeded from the first outcome and
weights three answers above all history. That is a product change to `harness/mastery.py`, and
this task was read-only on product code.

## Honest read

1. **Answer to the question asked: same mechanism, not a second one.** Six frozen signature
   facts all survive, and the EMA algebra explains why any `min_samples` value would leave a
   residue of this shape. The remaining disagreement worth having is whether 1.8 % of fires is
   an acceptable price, not what the 1.8 % is.
2. **The two runs are not paired.** The 32 came from seeds 20260902–41, the 11 from
   20261000–39. Different worlds, so "32 → 11" mixes the parameter change with sampling. The
   *shape* comparison is unaffected — a signature that reproduces on disjoint seeds is stronger
   evidence than one that reproduces on the same ones — but the size of the improvement carries
   the seed noise of two 40-seed samples, and the honest reading of it is the calibration
   report's paired slab, not this pair of columns.
3. **"Attempts at trigger" is an upper bound, and one number does not reconcile with yesterday's
   report.** The scorer counts every graded attempt on that competency dated on or before the
   fire date. `SimClock` pins every grade of a day to 19:00, so within-day ordering is not
   recoverable from the artifacts, and a capsule that continued past the escalation can add
   attempts to the count that the trigger never saw. The consequences are bounded: a fire at the
   floor cannot be inflated (9 is both the printed value and the minimum), so "5 of 11 fired at
   exactly the floor" is exact, and the median of 10 is an upper bound that can only move toward
   the floor. Attempt counts agree with the 2026-08-20 report where they overlap (median 8,
   range 8–11); **its accuracy figures do not** — that report gives mean 0.426 and 13 of 32 at
   ≥ 0.50, this scorer gives 0.443 and 15 of 32 on the same artifacts. I cannot reproduce the
   earlier method from what is on disk, so the two numbers are reported side by side rather than
   silently replaced, and the proposal's floor should be understood as reading end-of-day
   accuracy, not trigger-instant accuracy.
4. **Eleven events cannot support a story about archetypes.** The Poisson calculation for
   `disengaged` clears the usual bar, but it is one test chosen after seeing which archetype was
   over-represented, on 11 events, with no correction for having looked at six archetypes. Treat
   the response-rate explanation as a hypothesis with a cheap test (raise `response_rate` for one
   archetype in a scratch cohort and see whether its FP rate follows), not as a result.
5. **`ability_on_day` still ignores item difficulty.** Items carry difficulty 1–5; ground truth
   is one per-day ability with no item term. A capable child genuinely beaten by three hard items
   is scored here as detector noise. This remains the main way the eleven could be less unjust
   than they look, and it is the reason the classifier credits nothing at criterion 0.55 rather
   than proving nothing is creditable.
6. **The simulator does not guess on 3-option MCQs beyond `guess_probability`.** Real 3-option
   items float a blind student toward 0.33, so real EMAs run higher than simulated ones and the
   real cold-start FP rate is probably below 1.8 %. The same fact makes the proposed floor
   *more* conservative in production than the arithmetic above suggests.
7. **The proposed guard is unmeasured on purpose.** Every number in its table is arithmetic on
   printed rows — the eleven, or the thirty-two from the older sweep — or on published profile
   constants. None of it is a run of the guard, and replaying an accuracy threshold over stored
   fires is not the same as running a pipeline that would have taken different actions
   afterwards: a fire suppressed on day 3 changes nothing about the mastery state, but it does
   change the cooldown, the cohort failure list and every later day. The prediction is therefore
   a bound on the first-order effect only. It is offered so that it can be refuted, and the
   seeds and the three-way acceptance test are named before anyone has seen the result.
8. **A concurrent change to the daily close landed during this task.** `quality_graph.py` and
   `harness/calendar.py` were rewritten at 06:45–06:46 (delivery-day gating and outage
   detection) — after this sweep finished at 06:41. The struggle path this report is about was
   not touched at any point (all seven files date to 2026-08-20 23:09 or earlier), and the
   cohort figures are unaffected because the sweep runs no calendar overlay, so
   `_delivers_today` is true every day. Anyone re-running this report against a later tree
   should expect the struggle numbers to hold and should re-check the G5 block.
9. **Six of the eleven were fired at children who then stopped answering.** `stu15`, `stu16`
   and `stu17` are the `disengaged` archetype, and their false struggle alert lands on day 2–4,
   two to four days before `dropout_day = 6`. The pipeline tells that family "your child is
   struggling with line plots" and then, three days later, "your child has stopped practising".
   Nothing in the system connects the two messages, and the first one is wrong.

## Artifacts

- `.local_data/validation/results.json` — 40 rows (verdicts, tp/fp/low, interrupts, archetypes,
  sections, struggle fire dates, cohort signals) and `.local_data/validation/seed-<seed>/` —
  40 full local backends, read directly for the per-fire competency, attempts and accuracy.
- `.local_data/sweep/` — the surviving `min_samples = 8` backends, re-scored by the same tooling
  for the comparison column: `--results .local_data/sweep/results.json --residue-dir
  .local_data/sweep` reproduces 663 fires, 32 detector-noise, precision 0.952 [0.933–0.966] —
  the 2026-08-20 report's headline, from the current scorer.
- `scripts/score_fp_ground_truth.py` — `--residue-dir <base>` adds the per-fire table (seed,
  student, archetype, section, day index, attempts, cumulative accuracy, latent ability);
  `--criterion` overrides the default 0.50. Without `--residue-dir` it prints the same figures
  the 2026-08-20 report quoted, in a two-line-tighter header layout.
- `tests/benchmarks/test_fp_scoring.py` (15 cases) — the classifier and the justified-cohort
  logic, unchanged by this pass and still passing.
