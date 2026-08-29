# Struggle recall under a real school week — the window, not the horizon (2026-08-21)

**Both pre-declared gates pass, and the interesting number is the one that does not move.**
Over 42 calendar days of a five-day school week, struggle recall reaches 0.956 [0.915–0.977] of
low-ability students and the median detection lands on **scheduled day 4** — inside the first
school week. Recall climbs from 0.922 at day 14 to 0.956 at day 28 and then **flatlines: not one
of the last fourteen calendar days, ten of them school days, produces a single new detection**.
So the calendar bench's alarming 8/20 was a horizon artifact in the sense that more school days
did help — up to a point that arrives at day 28 — and it was not an artifact in the sense that
8 of 180 children are never flagged at all. The reason the curve stops is the simulator, not the
detector: by about the ninth school day the cohort's low-ability archetypes have learned their
way out of the struggling band, and after that there is nothing left to detect. All numbers come from a
real 20-seed run of the real pipeline (scripted model doubles, no network): 25,200 simulated
student-days in 326 s, $0.

## Setup

| Item | Value |
|---|---|
| Command | `nice -n 19 ./.venv/bin/python scripts/run_school_week_audit.py --seeds 20 --first-seed 20261200 --workers 3` |
| Runs | 20 held-out seeds (20261200–20261219) × 42 calendar days × 30 students = 25,200 student-days |
| Wall clock / cost | 326 s on 3 workers under `nice -n 19` / $0 — offline, scripted doubles |
| Overlay | Sat + Sun rest (`rest_weekdays = [5, 6]`), Carnaval 2026-09-14/15, Semana Santa 2026-09-21…25 — the two holiday blocks imported verbatim from `scripts/calendar_scoring.py`, the calendar bench's overlay. **No outage.** `mask_scheduled` ON: every family carries the calendar and `Settings.holiday_dates` is set |
| Shape of the term | 2026-09-01 (Tue) → 2026-10-12 (Mon); **23 of the 42 calendar days are school days** — 4.6 school weeks. 690 sessions per run in every seed (23 × 30, deterministic); 1,669 responses in seed 20261200, the one seed whose totals the bench prints — the other nineteen differ by response-rate randomness and are in `results.json`, not in any table here |
| Cohort | `simulator/cohort.build_cohort`, unchanged: 30 students, the eight archetypes, matrix (a) in `scripts/README.md`. 9 low-ability students per seed (4 `struggling` + 5 `cohort_cluster`) = **180 scored students** |
| Settings deviating from defaults | `holiday_dates` only. `escalation_min_samples` is 9, the tree's current default |
| Source tree | fingerprint `1a8fb984ed28` (SHA-256 over all of `src/repaso/**/*.py`) |

**What "latency" means here.** These students are low-ability from day 0 by construction, so
onset is term start and latency is measured from it: a detection on the first school day has
latency 1. Both units are reported — **scheduled** days count only days the school was open,
**calendar** days count everything. A detection on 2026-09-16 is scheduled day 10 and calendar
day 16; the two diverge by exactly the rest days and holidays in between.

### Gates, declared before the first run

`RECALL_GATE = 0.95`, `LATENCY_GATE = 6` and the day-14/28/42 checkpoints were written into
`scripts/run_school_week_audit.py` before it was ever executed, and the script prints its own
verdicts.

| Gate | Threshold | Why this number |
|---|---|---|
| **R** struggle recall within the 42-day horizon | ≥ 95 % of low-ability students | The same bar the pre-registered G1 uses, moved from "seeds where every child was caught" to "children caught", because a parent is not a seed |
| **L** median detection latency | ≤ 6 **scheduled** days | Roughly one school week plus a day. Counted in school days because that is when evidence can arrive at all; a bar in calendar days would silently reward or punish where the holidays fell |

**Held-out, with two asterisks.**

1. Seed 20260901 — the in-sample calibration seed, never a measurement — was run once as this
   bench's smoke test, and it showed 9/9 recall at a median of 4 scheduled days. The gate
   constants were already in the file before that run; no threshold moved after seeing it.
2. **Seed 20261200 is not strictly held out.** Concurrent work on the calendar bench spent it
   the same day as its own smoke test — `scripts/README.md` records this — so it had been
   executed by a different bench before this one ran. No threshold here was chosen while looking
   at it, and dropping it changes nothing:
   `run_school_week_audit.py --seeds 19 --first-seed 20261201` gives recall **163/171 = 0.953
   [0.910–0.976]**, median latency **4** scheduled days, complete-recall seeds 7/19 → 13/19 →
   13/19 across the same three checkpoints, and the identical p90/max in both units. Both gates
   still pass; every claim below survives the drop.

The other nineteen seeds had never been run by anything, and the whole block 20261200–20261219
is now spent.

## Gates vs reality

| Gate | Result | Verdict |
|---|---|---|
| R recall within 42 calendar days | 172/180 = **0.956 [0.915–0.977]** | **passed** — on the point estimate |
| L median detection latency | **4 scheduled days** (bar 6) | passed |

The recall interval is worth staring at: the point estimate clears 0.95, the lower bound
(0.915) does not. Twenty seeds is not enough to *establish* 95 % recall; it is enough to fail it,
and it did not.

## The recall curve over calendar time

| Horizon | School days elapsed | Detected | Of | Recall | 95 % CI | Seeds catching all 9 |
|---|---|---|---|---|---|---|
| day 14 | 9 | 166 | 180 | 0.922 | [0.874–0.953] | **8/20** |
| day 28 | 13 | 172 | 180 | **0.956** | [0.915–0.977] | **14/20** |
| day 42 | 23 | 172 | 180 | 0.956 | [0.915–0.977] | 14/20 |

Two facts sit in that table.

1. **Days 15–28 are worth 6 children and 6 seeds.** Four extra school days move seed-level
   complete recall from 8/20 to 14/20. That is the horizon artifact, and it is large.
2. **Days 29–42 are worth nothing at all.** Ten more school days, ten more sessions per student,
   6,000 more delivered sessions across the twenty seeds, and not one new detection. The last struggle
   escalation in the entire 25,200-student-day run lands on scheduled day 13 = calendar day 28.

The 8/20 at day 14 collides with the calendar bench's headline, and the collision is arithmetic
rather than setup: that bench ran 28 calendar days (13 school days) *with a three-day outage*
and scored 8/20 on the same ledger row, while this bench reaches 8/20 after only 9 school days
and no outage. The same 13 school days without an outage score 14/20 here.
Three silent school days out of thirteen cost roughly six seeds of complete recall — a plausible
attribution, on different seeds, and one the calendar bench's own `health` arm is better placed
to settle than this one.

## Detection latency

Term start = day 1. The eight never-detected students are excluded from the percentiles, which
is the generous convention; counting them as infinite moves neither p50 (still 4) nor p90 (still
8), because 172 of 180 sit below both ranks.

| Signal | Found | Never | p50 sched | p90 sched | max sched | p50 cal | p90 cal | max cal |
|---|---|---|---|---|---|---|---|---|
| struggle (all low-ability) | 172 | 8 | **4** | 8 | 13 | **4** | 10 | 28 |
| `struggling` ×4/seed | 75 | 5 | 4 | 7 | 10 | 4 | 9 | 16 |
| `cohort_cluster` ×5/seed | 97 | 3 | 4 | 8 | 13 | 4 | 10 | 28 |
| cohort signal for 4-b (1/seed) | 16 | 4 | 5 | 7 | 9 | 7 | 9 | 11 |

By scheduled day, every struggle detection in the run:

| Scheduled day | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 12 | 13 |
|---|---|---|---|---|---|---|---|---|---|---|
| Detections | 33 | 55 | 36 | 20 | 10 | 9 | 3 | 3 | 2 | 1 |
| Cumulative | 33 | 88 | 124 | 144 | 154 | **163** | 166 | 169 | 171 | 172 |

Nothing fires before scheduled day 3 — `escalation_min_samples = 9` needs about three school
days of practice on one competency to reach nine attempts — and 163 of 172 (95 %) land by
scheduled day 8. In calendar terms the median child is flagged on **2026-09-04, the first
Friday**; the 90th-percentile child on **2026-09-10**; the slowest on **2026-09-28**, four
calendar weeks in.

The section-level cohort signal is slower and less reliable than the individual one: 16 of 20
seeds raise it, at a median of 5 school days (7 calendar days) and never later than 9 school
days. In 4 seeds the planted cluster in `colegio-demo-4-b` never trips the k = 3 family floor
inside the whole term. Exactly **1** cohort signal fired outside 4-b across all 20 seeds.

## Why the curve stops

The detector is not slow relative to its window; the window is short and it closes.

Ability is `ability_on_day(profile, day)` with `day` the 0-based index from 2026-09-01, so the
crossings below are dates, and the school-day counts are `scheduled_index` on those dates —
the same function the bench uses, pinned by `tests/benchmarks/test_school_week_audit.py`.

| Archetype | Latent ability | Last day below 0.40 | School days by then | Last day below 0.50 | School days by then |
|---|---|---|---|---|---|
| `cohort_cluster` | 0.25 + 0.02·day − 0.12 dip | 2026-09-08 (day 7) | **6** | 2026-09-13 (day 12) | **9** |
| `struggling` | 0.20 + 0.02·day − 0.10 dip | 2026-09-10 (day 9) | **8** | 2026-09-15 (day 14) | **9** |

`ability_on_day` is linear and unbounded below the clip, so a simulated struggling child gains
0.02 of ability every calendar day whether or not school was open — weekends and Semana Santa
included. On 2026-09-11 the `struggling` profile reaches 0.40, the value of `STRUGGLING_CEILING`
itself; on 2026-09-16 it passes 0.50; by the end of the horizon it is clipped at 1.00. **The
second half of this term contains no low-ability students**, which is the whole explanation for
a flat curve after day 28: the detector runs out of subject, not out of time.

That leaves 95 % of detections (163 of 172, by scheduled day 8) inside a window holding at most
**9 school days** of genuinely low ability. The detector uses nearly all of it.

## Honest read

1. **Direct answer: the 28-day alarm was mostly a horizon artifact, and what remains is not
   demonstrably a product problem.** Recall recovers 0.922 → 0.956 between day 14 and day 28,
   seed-level complete recall 8/20 → 14/20, and then stops. Both gates pass. But "recall
   recovers by 42" is false as stated — it recovers by 28 and the last two school weeks add
   nothing.
2. **The experiment that would decide it is not in the cohort.** The question a school actually
   asks is "does the system catch a child who is still stuck in week six?" This audit cannot
   answer it, because no such child exists: both low-ability archetypes climb past 0.40 by the
   eighth or ninth school day and reach ability 1.00 before the term ends. The 8 misses are
   therefore ambiguous — a miss might mean "we failed her" or "she stopped needing us in the
   second week". Until the simulator gains a persistent-difficulty archetype (constant ability,
   or a learning rate near zero), the 4.4 % miss rate cannot be read as harm. **That archetype
   is the single highest-value addition to `simulator/archetypes.py` this bench has surfaced,
   and it is a product change this task was not allowed to make.**
3. **The misses are not evenly spread, and 20 seeds cannot say whether that matters.** Eight
   students missed across six seeds — two seeds miss two children each. By archetype it is 5 of
   80 `struggling` (0.938) against 3 of 100 `cohort_cluster` (0.970), which is the *lower*-ability
   group doing worse. On these counts that difference is noise; naming it here is a hedge
   against quietly reporting the pooled number later.
4. **The latency gate is measured on survivors.** p50 and p90 over the detected 172 happen to
   equal p50 and p90 over all 180, so the convention costs nothing here — but that is luck, not
   design. At a miss rate above 10 % the same gate would flatter itself badly, and the gate
   should be restated as "≤ 6 scheduled days for ≥ 90 % of low-ability students" before it is
   ever used on a worse detector.
5. **The overlay is stylized in the same three ways the calendar report named.** Rest days are
   uniform across every family, holidays are a flat date list with no per-school variation, and
   there is no outage here at all. A single-family trip, a school that keeps a different
   Carnaval, and a section-scoped outage are all untested. The `SIGNAL_WINDOW_DAYS = 14`
   response window is also unchanged, and Semana Santa's 9 days fit inside it — a month-long
   recess would not, and this 42-day horizon still does not test one.
6. **Product code changed under the run, and the run did not move.** A concurrent change to the
   daily close (`quality_graph.py` delivery-day gating, `harness/calendar.py` outage detection)
   landed 90 seconds after the first execution of this bench started. The bench was re-run from
   scratch on the settled tree (`1a8fb984ed28`), and the two `results.json` files are **identical
   field for field except `elapsed_seconds`** — same 172/180, same histogram, same 16 cohort
   signals, same 8 misses in the same seeds. The struggle path was untouched by that change,
   and this is the measurement that says so rather than the argument that says so.
7. **The bench imports another script's constants.** `START`, `REST_WEEKDAYS`, `HOLIDAYS` and
   `school_day` come from `scripts/calendar_scoring.py` so that "the same overlay as the
   calendar bench" is a fact rather than a copied literal. That file was being edited by other
   work during this task. The coupling is deliberate and the four names are stable, but a rename
   there breaks this bench, and `tests/benchmarks/test_school_week_audit.py` asserts the overlay
   it expects for exactly that reason.
8. **What a term looks like from a parent's side — framed, not decided.** For the 95.6 % who are
   detected: half of the families hear within **4 school days** — under one school week — 90 %
   within 8 school days (about 1.6 school weeks), and the slowest within 13 school days, which
   is 4 calendar weeks because two holiday blocks sit in the middle. For the other 4.4 %,
   nothing arrives in six weeks. The section-level signal a teacher would act on takes a median
   of 5 school days and fails to appear at all in 1 seed in 5. Whether "most families in the
   first school week, one in twenty-three never, and one section in five with no teacher-level
   signal" is acceptable for a pilot is a decision for the school and for Carlos, not for this
   report; what the report can say is that the first number is fast, the second is
   uninterpretable until a persistently-struggling archetype exists, and the third is the one
   least discussed so far.
9. **Nothing here was tuned.** No parameter moved, no threshold was chosen after a number was
   seen, and the 20 seeds are fresh: the hygiene table in
   `docs/reports/calibration-validation-2026-08-20.md` reserves 20260901, 20260902–41,
   20260950–64, 20261000–39 and 20261100–19, and this range starts at 20261200. Two benches
   reached for that block on the same morning — the calendar bench took 20261200 as a smoke
   test, this one took 20261200–19 as its sweep — which is a coordination failure, not a
   measurement one, and it is why the drop-one check exists. **The next unspent block for
   either bench starts at 20261220**, and the 40 seeds this report's companion names for the
   proposed corroboration floor (20261300–39) are clear of both.

## Artifacts

- `.local_data/school_week/results-drop-first.json` — the 19-seed drop-one check, 334 s.
- `.local_data/school_week/results.json` — 20 rows: scheduled days, sessions, responses, one
  record per low-ability student (archetype, section, detected, fire date, latency in both
  units) and the section's cohort signal with its own latencies and any stray signals.
- `.local_data/school_week/seed-<seed>/` — 20 full local backends, one per run.
- `scripts/run_school_week_audit.py` — the bench; prints its own gate verdicts, recall curve,
  latency distributions and per-scheduled-day histogram.
- `tests/benchmarks/test_school_week_audit.py` (19 cases) — the scheduled/calendar day
  arithmetic across weekends, Carnaval and Semana Santa, the nearest-rank percentiles, the
  recall cutoffs, and the assertion that the overlay is the calendar bench's overlay.
