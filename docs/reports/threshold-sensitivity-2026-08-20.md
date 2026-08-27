# Threshold sensitivity — do the shipped escalation knobs sit mid-plateau? (2026-08-20)

**One shipped threshold is demonstrably mispositioned: `escalation_min_samples = 8` sits
one notch below its plateau, and moving it to 9 removes nine of the fourteen
false-positive students at zero recall cost.** The other three defaults survive, but not
all for flattering reasons — the cooldown is genuinely flat and 7 days sits in the
interior; `STRUGGLING_CEILING` has no plateau at all, it is a monotone precision-recall
trade dial on which 0.4 misses the tolerance band by 0.001; and
`grader_confidence_threshold` is behaviorally two-valued against the scripted judge, so
its "cliff at 0.95" measures the test double more than it measures the product. All
numbers come from 390 runs of the real pipeline driven by simulated students and scripted
model doubles: 163,800 simulated student-days in 1,212 s (20 min 12 s) of wall clock, $0,
no network.

## Setup

| Item | Value |
|---|---|
| Command | `python scripts/run_sensitivity.py --seeds 15 --first-seed 20260950 --workers 6` |
| Grid | 26 grid points across 4 parameters × 15 held-out seeds = 390 runs, one parameter moved per run |
| Runs | 390 × 420 student-days = 163,800 simulated student-days through the real pipeline |
| Wall clock / cost | 1,212 s = 20 min 12 s (≈3.1 s per run on 6 workers, ≈18.6 s of CPU) / $0 (offline, scripted model doubles, no network) |
| Seeds | 20260950–20260964 — disjoint from the 40-seed sweep (20260902–20260941) and from the in-sample calibration seed (20260901) |
| Metric | pooled per-student struggle precision and recall (TP = fired ∩ low-ability archetype, FP = fired outside it), and total interrupts p50 per 420 student-days |
| Metric source | definitions mirrored from `run_seed_sweep.run_one`; `LOW_ARCHETYPES` is pinned to the simulator's own `cohort.LOW_ABILITY` by test |
| Plateau rule | widest contiguous run of grid values with precision ≥ (max precision − 0.03) **and** recall ≥ 0.95 |
| Source tree | fingerprint `b9ac22a35222` (`find src -name '*.py' \| sort \| xargs shasum -a 256 \| shasum -a 256`), identical when sampled mid-run and at completion; workers are spawned once at pool start, so all 390 runs executed one tree |
| Settings deviating from defaults | exactly one per run, by construction |

## How each knob is delivered, and the trap in one of them

Two parameters are `Settings` fields and travel as constructor arguments. Two are module
constants, so the runner rebinds them **inside the worker process** before the pipeline
runs. The two constants do not behave the same way, and the difference decides whether a
sweep measures anything at all.

- **`STRUGGLING_CEILING` is read at call time.** `mastery.classify()` looks the name up as
  a module global on every call, so `setattr(mastery, "STRUGGLING_CEILING", x)` takes
  effect on the next classification with no re-import.
  `test_classify_reads_struggling_ceiling_at_call_time` verifies exactly this — it
  classifies EMA 0.45 as DEVELOPING, rebinds the ceiling to 0.5, and gets STRUGGLING back
  from the same call.
- **`DEFAULT_COOLDOWN_DAYS` is captured at import time by its consumers.**
  `core/orchestration/response_graph.py` and `simulator/verdicts.py` both do
  `from repaso.core.harness.escalation_triggers import DEFAULT_COOLDOWN_DAYS`, so each
  holds its own binding. Patching only the defining module leaves the live call site —
  `build_signals(..., DEFAULT_COOLDOWN_DAYS)` in `response_graph.adapt` — reading the
  original 7. That is a silent no-op: the sweep would have run, produced a perfectly flat
  curve, and the flat curve would have meant "the patch never landed", not "the system is
  insensitive". `rebind_constant` therefore patches all three modules, and
  `test_patching_only_the_source_module_misses_the_call_site` pins the trap so it cannot
  come back.

Worker processes are reused across grid points, so `apply_constants` also **resets every
constant not under test** to its shipped default on every job. Without that, values would
leak forward from whichever job the worker ran last.

## `escalation_min_samples` — the shipped 8 is one notch below the plateau

```
escalation_min_samples  (7 values x 15 seeds)
   value  precision   recall   p50    tp   fp  flag
       5      0.699    1.000    69   135   58
       6      0.758    1.000    62   135   43
       7      0.833    1.000    57   135   27
       8      0.906    1.000    53   135   14  DEFAULT
       9      0.964    1.000    52   135    5  plateau
      10      0.971    1.000    49   135    4  plateau
      12      0.993    0.985    44   133    1  plateau
escalation_min_samples: plateau [9, 12] (3/7 values); default 8 OUTSIDE
```

Precision climbs monotonically from 0.699 to 0.993 while recall stays perfect — every one
of the 135 low-ability students (9 per seed × 15 seeds) is reached at every value up to
10. There is no recall price to pay for 9 or 10, so the whole left half of this grid is
strictly dominated:

| Move | Precision | FP students | Seeds with ≥1 FP | Recall | Interrupts p50 |
|---|---|---|---|---|---|
| 8 (shipped) | 0.906 | 14 | 10/15 | 135/135 | 53 |
| → 9 | 0.964 | 5 | 5/15 | 135/135 | 52 |
| → 10 | 0.971 | 4 | 4/15 | 135/135 | 49 |
| → 12 | 0.993 | 1 | 1/15 | 133/135 | 44 |

Recall only breaks at 12, and then on 2 of 15 seeds. The plateau's right edge is also the
grid's right edge, so the safe reading is that **10 is the interior point**: it holds
complete recall, cuts FP students from 14 to 4, and drops the median interrupt load by
four per 420 student-days.

This is also the parameter the harness README declares **in-sample** — 8 was tuned by eye
on calibration seed 20260901. Finding it one notch off on 15 held-out seeds is exactly
the signature you would predict for a by-eye fit, and it is the strongest argument in this
report for not tuning thresholds on a single seed again.

## `STRUGGLING_CEILING` — not a plateau at all, a trade dial

```
STRUGGLING_CEILING  (9 values x 15 seeds)
   value  precision   recall   p50    tp   fp  flag
     0.3      0.937    0.985    45   133    9  plateau
   0.325      0.924    0.993    49   134   11  plateau
    0.35      0.918    0.993    51   134   12  plateau
   0.375      0.905    0.993    53   134   14
     0.4      0.906    1.000    53   135   14  DEFAULT
   0.425      0.900    1.000    53   135   15
    0.45      0.877    1.000    54   135   19
   0.475      0.849    1.000    54   135   24
     0.5      0.839    1.000    61   135   26
STRUGGLING_CEILING: plateau [0.3, 0.35] (3/9 values); default 0.4 OUTSIDE
```

The verdict line says OUTSIDE, and reporting it as a real finding would be dishonest.
Maximum precision on this grid is 0.937, so the tolerance band floor is 0.907; the
default scores **0.906 — one thousandth below the cut**. Nothing in the underlying
behavior changes across that boundary.

What the curve actually shows is that this knob has no flat region in either direction:
precision falls monotonically from 0.937 to 0.839 as the ceiling rises, and recall rises
from 0.985 to 1.000 over the same span. It is a pure trade dial. The shipped 0.4 is the
lowest value on the grid that still reaches **every** low-ability student in **every**
seed; buying the 0.031 of precision available at 0.30 costs two students in two seeds.
Given that a missed struggling child is the failure this system exists to prevent, 0.4 is
a defensible place to stand — but it should be described as a chosen trade-off, never as
"mid-plateau".

## `DEFAULT_COOLDOWN_DAYS` — flat exactly where the mechanism says it must be

```
DEFAULT_COOLDOWN_DAYS  (5 values x 15 seeds)
   value  precision   recall   p50    tp   fp  flag
       3      0.906    1.000    63   135   14  plateau
       5      0.906    1.000    57   135   14  plateau
       7      0.906    1.000    53   135   14  plateau DEFAULT
      10      0.906    1.000    50   135   14  plateau
      14      0.906    1.000    46   135   14  plateau
DEFAULT_COOLDOWN_DAYS: plateau [3, 14] (5/5 values); default 7 INSIDE (interior)
```

Precision, recall, TP and FP are **identical at all five values**, which is what the
mechanism predicts: the cooldown gates *refires*, so it changes how often a family is
paged, never which students get flagged. The metric that moves is the one that should —
median interrupts fall monotonically from 63 to 46, a 27 % reduction in paging load
across the grid, with no detection cost whatsoever on a 14-day horizon.

That p50 movement is also the control that makes this row trustworthy. A flat
precision/recall curve is exactly what a **failed patch** looks like, and
`DEFAULT_COOLDOWN_DAYS` is the one constant whose consumers capture it at import time. If
the rebinding had missed `response_graph`, every column here would have been flat
including p50. It is not: the patch demonstrably reaches the call site.

The honest caveat is horizon, not mechanism. At 14 days a 14-day cooldown allows at most
one refire, so "no detection cost" is partly an artifact of the window; the interrupt-load
saving is real, the safety of a long cooldown over a full term is not measured here.

## `grader_confidence_threshold` — one cliff, and it belongs to the test double

```
grader_confidence_threshold  (5 values x 15 seeds)
   value  precision   recall   p50    tp   fp  flag
     0.7      0.906    1.000    53   135   14
     0.8      0.906    1.000    53   135   14
    0.85      0.906    1.000    53   135   14  DEFAULT
     0.9      0.906    1.000    53   135   14
    0.95      1.000    0.926   263   125    0
grader_confidence_threshold: NO PLATEAU (no value clears the floors); default 0.85 OUTSIDE
```

Read the verdict line carefully before believing it. 0.70 through 0.90 are **identical on
every column** — same TP, same FP, same median interrupts. The rule reports NO PLATEAU because the
cliff point at 0.95 scores precision 1.000, which lifts the tolerance band floor to 0.97
and disqualifies the flat band, while 0.95 itself fails the recall floor (0.926). Both
halves of the rule fire, so nothing survives. **This is a rule artifact on a step
function, not evidence against the default.** Operationally the default sits in the middle
of a four-point identical band, one grid step below a cliff.

The cliff is severe and worth naming. At 0.95 every open answer is quarantined: median
interrupts jump from 53 to **263** (5.0×, range 230–282), and because a quarantined grade
carries `correct=None`, `apply()` never feeds it to `update_mastery`. Open-item evidence
stops reaching mastery entirely, so eight of fifteen seeds fail to reach at least one
low-ability student (recall 0.926) — while precision reads a perfect 1.000, since the
withheld evidence was also what pushed high-ability students' EMA down. A dashboard would
show that configuration as a precision win.

The reason this row proves less than it appears to: the offline demo clock primes the
scripted judge with **confidence 0.30 for hedged answers and 0.92 for everything else**.
Two values, so this grid has exactly two behavioral regimes, and the cliff sits where it
does because 0.92 lies between 0.90 and 0.95. Against a real grader with a continuous
confidence distribution the curve would be a slope, and its shape is not measured here.

## Default-point cross-check

All four parameters include their shipped default in the grid, so four independent
15-seed groups — scheduled at different times, on reused worker processes — ran the
identical shipped configuration:

```
default-point cross-check (4 parameters): identical
      escalation_min_samples=8      tp=135   fp=14   recall=1.000 p50=53
          STRUGGLING_CEILING=0.4    tp=135   fp=14   recall=1.000 p50=53
       DEFAULT_COOLDOWN_DAYS=7      tp=135   fp=14   recall=1.000 p50=53
 grader_confidence_threshold=0.85   tp=135   fp=14   recall=1.000 p50=53
```

That is one check doing two jobs: it is a determinism replication (60 runs, four
schedules, same counts), and it is the leak detector for constant rebinding on reused
workers — a value surviving from a previous job would have shown up here as a mismatch.

A second, independent replication was run afterwards on the headline parameter alone
(`--params escalation_min_samples`, 105 runs, 317 s): every cell of that table came back
identical, and comparing the raw rows one by one, **0 of 105 runs differed** on tp, fp,
low or interrupts. Same seeds, same tree, fresh worker pool.

For calibration against the main sweep, the shipped configuration on these 15 seeds scores
precision 0.906 and recall 1.000 (135/135); the 40-seed sweep on 20260902–20260941 scored
0.918 [0.886–0.941] and 0.994. Different seeds, consistent picture.

## Honest read

1. **These are four 1-D slices, and two of the four knobs gate the same predicate.**
   `struggle_trigger` fires on `level is STRUGGLING` **and** `attempts >= min_samples`, so
   `STRUGGLING_CEILING` and `escalation_min_samples` are not independent: the sample floor
   was swept at ceiling 0.4 and the ceiling at floor 8. The "move 8 → 10" reading is only
   established on that line. **Named follow-up: the 2-D slab `min_samples ∈ {8, 9, 10} ×
   ceiling ∈ {0.35, 0.40, 0.45}`, 9 cells × 15 seeds = 135 runs, ≈7 min at the measured
   3.1 s/run.** It is the cheapest thing in this report's backlog and it is the one that
   can overturn the recommendation.
2. **The seeds are held out; the students are not real.** 20260950–20260964 never touched
   threshold tuning, but every one of them is the same simulator: 8 archetypes in fixed
   proportions with deterministic ability curves that leave a clean gap between the
   low-ability band (0.14–0.51 over days 0–13) and everyone else (0.65–1.00). Plateau
   widths measured across a gap like that are optimistic by construction — a real cohort
   is a continuum, and a continuum blurs precisely the boundary these thresholds sit on.
   Nothing here says the plateau exists in a classroom; it says the plateau exists in the
   generator, and that the shipped default is off-centre even there.
3. **The precision axis inherits an assumption this run did not re-test.** TP/FP are
   scored against archetype labels, mirroring `run_seed_sweep`. Today's ground-truth report
   (`fp-groundtruth-2026-08-20.md`) established on the 40-seed sweep that label-FPs are
   genuine detector noise — all 32 had true ability ≥ 0.67 at fire time — which is why the
   axis is meaningful at all. The 14 FPs at this run's default point were **not**
   individually re-scored against `ability_on_day`; that is borrowed evidence, not a
   measurement made here.
4. **The plateau rule is arbitrary in two places, and two verdicts turn on it.** The
   tolerance (0.03) and the recall floor (0.95) were fixed before the runs and are reported
   as computed. But `STRUGGLING_CEILING = 0.4` is ruled OUTSIDE by 0.001 of precision, and
   `grader_confidence_threshold` is ruled NO PLATEAU because the cliff point holds the
   maximum precision and drags the band above the flat region. Both verdicts are literally
   correct and neither means what the label suggests. The rule was not retuned afterwards
   to make the defaults look better, and it should not be.
5. **Every recall number lives on a 14-day horizon.** A high sample floor is expensive
   early and cheap later — `min_samples = 12` loses two students in two seeds here, and
   would likely lose none over a term, while its FP reduction persists. Symmetrically, a
   14-day cooldown looks free at 14 days because it permits at most one refire inside the
   window. The interrupt-load savings are measured; the long-horizon safety of the
   right-hand end of either grid is not.
6. **`interrupts p50` is paging load, not decisions.** It sums escalations, one-tap
   quarantine approvals and per-family cohort deliveries — the same definition as the
   sweep, kept deliberately so the two reports compare, and still a proxy that lumps a
   one-tap approval together with a struggle packet.
7. **What this changes, and what it does not.** The concrete ask is to move
   `escalation_min_samples` from 8 to 10 (9 is the conservative half-step), then re-run the
   pre-registered gates on the 40-seed sweep, because G2 — zero struggle FPs in ≥ 95 % of
   seeds — failed at 19/40 and this sweep shows FP-carrying seeds falling from 10/15 to
   4/15 across that move. That is an indication on 15 different seeds, **not** a gate
   re-score: G1 and G2 are defined on 20260902–20260941 and only a re-run there can move
   them. Nothing in this report justifies touching the other three defaults.
8. **Runtime, honestly.** This work was budgeted at ≈6–8 min for ~500 runs on the
   assumption of ≈4 s per run; 390 runs took 20 min 12 s, because a run costs ≈18.6 s of
   CPU (≈3.1 s of wall clock on 6 workers). The 15-seed depth was kept rather than cut to
   10 per value — the extra 13 minutes bought per-point counts tight enough that the
   `min_samples` gap (14 FP students vs 5) is not a coin-flip. Budget a repeat at ≈3.1 s ×
   (grid points × seeds) of wall clock on 6 workers.

## Artifacts

- `.local_data/sensitivity/results.json` — 390 run rows (param, value, seed, tp, fp, low,
  interrupts) plus the pooled report and the elapsed time. Every ASCII block above is
  rendered from those rows by `summarize` / `format_table` / `format_default_check` — the
  same three calls `run_sensitivity.main` makes, so re-running the command reprints them.
- `scripts/run_sensitivity.py` — runner and CLI; `scripts/sensitivity_grid.py` — grids,
  constant rebinding, pooling, plateau maths, table rendering.
- `tests/benchmarks/test_sensitivity_helpers.py` (11 tests) and
  `tests/benchmarks/test_sensitivity_plateau.py` (12 tests) — the patching mechanism, the
  from-import trap, grid/default agreement with the shipped values, pooling, and the
  plateau rule.
