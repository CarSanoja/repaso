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

## Addendum — G7 characterized (same day)

**G7's four seeds were not variance. They were a defect in the measuring instrument, and
it was corrupting ten seeds — the gate only noticed on four.** The offline demo clock
primes the shared scripted judge with the grade it wants back *before* handing the answer
to `handle_answer`. When that answer is a prompt injection, `handle_answer` quarantines it
at the screener and returns before the grader ever runs, so the primed payload is left
sitting in the judge's process-global FIFO. From that moment every later open answer in
the run pops the *previous* open answer's payload. The product path — screener, grader,
confidence threshold, quarantine store — was correct throughout; the harness was grading
the right answers with the wrong scripted verdicts. Characterization, fix, regression
tests and a re-swept 40 seeds, all real pipeline with simulated students and a scripted
judge: 16,800 student-days in 221 s, plus a 191 s fix-off isolation run, $0 for both.

### Setup

| Item | Value |
|---|---|
| Command | `python scripts/run_seed_sweep.py --seeds 40 --workers 6 --base-dir .local_data/sweep-g7 --out .local_data/sweep-g7/results.json` |
| Isolation | same working tree, pre-fix `_play_day` reinstalled in-process, 40 seeds |
| Runs | 40 seeds × 420 student-days = 16,800 student-days, twice |
| Wall clock / cost | 221 s fixed + 191 s fix-off / $0 (offline, scripted doubles) |
| Fix under test | `demo_clock._settle_open_prime` and `_assert_primes_drained`; `AutoStubModel.pending` / `drop_pending` |
| Settings deviating from defaults | none |
| Note | 221 s vs the original 132 s is machine contention, not the fix — a second sweep was running concurrently |

### The mechanism, traced on seed 20260910

The demo clock walks students in ledger order; `stu28`/`stu29` are the ambiguous
(hedging) students and `stu30` is the injector, who injects on days 2 and 3.

| Day | Student | Primed confidence | Judge popped | Result |
|---|---|---|---|---|
| 2 | stu29 | 0.30 hedged | 0.30 | quarantined — correct |
| 2 | stu30 | 0.92 | *never called* (screener intercepted) | **prime stranded, queue depth 1** |
| 3 | stu28 | 0.30 hedged | 0.92 | **auto-graded — the G7 miss** |
| 3 | stu29 | 0.92 | 0.30 | quarantined on a *non*-hedged answer |
| 3 | stu30 | 0.92 | *never called* | queue depth 2 for the rest of the run |

Because the queue never drains, the last two primes of the run are never consumed, so
`hedged quarantines = planted_hedged − (hedged primes among the final two)`. That is why
the mismatch was always small and always in one direction.

Leaks need the injector's scripted injection to land on an *open* item. Measured on the
corrected runs across all forty seeds, that happens on **ten** of them, and where it
happens it happens on both injection days — the drop distribution is exactly `{0 primes:
30 seeds, 2 primes: 10 seeds}`, never one. G7 caught four of those ten; on the other six
the same off-by-two misalignment ran from day 2 to the end of the run, but neither
stranded prime was a hedged one, so the gate saw matching totals and passed.

### The fix

Three small changes, all inside the simulator:

- `AutoStubModel.pending(name)` / `drop_pending(name)` — the scripted judge can now be
  asked what it is still holding.
- `demo_clock._settle_open_prime` — after every open answer, the prime is required to
  have been consumed. If it was not, it is dropped rather than left to shift the next
  student, and counted in a new `DemoClockResult.dropped_open_primes`. A hedged answer
  now increments `planted_hedged` only when it actually reached the judge, so the double
  stays strict in both directions: an answer intercepted upstream cannot be counted as a
  hedge that "should have" quarantined.
- `demo_clock._assert_primes_drained` — a day-end tripwire raising `StalePrimeError` if
  anything is still queued. With per-answer settling this is unreachable today; it is
  there so the next prime site added to the harness fails loudly instead of silently
  skewing every open grade after it.

The bug forced the question of whether the prime should be keyed per student instead.
It cannot be, without changing product code: `AutoStubModel.structured_output` sees only
the output type, the prompt and the system prompt, and `grader.open_prompt` carries the
item and the answer text but no student id. Keying per student would have meant editing
the grader prompt to satisfy the test double — the wrong trade. Draining and asserting
achieves the same strictness without the harness reaching into the product.

### Gates, fix-off vs fix-on, same tree

| Gate | Fix off | Fix on | Δ |
|---|---|---|---|
| G1 struggle recall complete | 36/40 | 38/40 | +2 |
| G2 zero struggle false positives | 16/40 | 19/40 | +3 |
| G3 refire gaps ≥ 7 d | 40/40 | 40/40 | — |
| G4 engagement recall | 40/40 | 40/40 | — |
| G4 engagement FP-free | 36/40 | 35/40 | −1 |
| G5 cohort only 4-b, ≤ 1/week | 29/40 | 30/40 | +1 |
| G6 injections = planted | 40/40 | 40/40 | — |
| **G7 hedged = planted** | **36/40** | **40/40** | **+4** |
| G8 fast-guess exact | 40/40 | 40/40 | — |

The fix-off column reproduces the original sweep's nine gate counts exactly, including
the same four G7 seeds (20260910, 20260911, 20260914, 20260924). Concurrent core work
landing in the same tree today therefore had no effect on these numbers, and the whole
delta is attributable to this one fix.

The delta also checks out against the mechanism. Eight seeds changed verdict on some
gate — 20260906, 20260908, 20260910, 20260911, 20260914, 20260924, 20260930, 20260936 —
and **all eight are inside the ten-seed leaking set**. No seed that never leaked a prime
moved on any gate. The two leaking seeds that did not move (20260902, 20260903) are the
ones where the shifted grades happened not to change any escalation outcome.

Pooled struggle metrics moved with it: precision **0.918 [0.886–0.941]** (358 TP, 32 FP)
against the original **0.892 [0.858–0.919]** (356 TP, 43 FP); recall **0.994
[0.980–0.998]** against **0.989 [0.972–0.996]**. Interruptions per 420 student-days are
unchanged at p50 = 52, p95 = 71.

### Honest read

1. **G7 is 40/40 and the double is now strict.** The gate can no longer pass by accident:
   a hedged answer is counted only once the judge has actually graded it, and a prime that
   never reaches the judge is dropped and reported rather than carried forward.
2. **This was an instrument defect, not a product defect.** Nothing in the shipped
   quarantine path was wrong. That is the good news and also the uncomfortable news: for
   one day, G7's four failing seeds stood on the board as a product failure, and they
   were the harness's.
3. **The measurement error was not confined to G7.** Ten seeds carried the off-by-two
   shift, so on those runs the open-item grades — and the mastery, spacing and escalation
   decisions downstream of them — were computed from the wrong correctness from day 2
   onward. G2 recovered on 20260906, 20260911 and 20260936, and only one of those
   three was a G7 failure. G7 was the alarm, but it was under-sensitive by more than half:
   any gate reading through open grades was being scored on a corrupted trajectory in six
   seeds where G7 reported "as expected".
4. **G4's FP-free count went 36 → 35, and that is reported as a loss, not smoothed over.**
   Seed 20260908 now fires engagement on an active student it previously spared. It is one
   seed on a gate whose threshold is ≥ 90 %, so G4 still passes, but the honest statement
   is that correcting the grades made one seed worse and three better on G2 — the
   post-fix numbers are the true ones in both directions.
5. **G1, G2 and G5 remain open and remain the real work.** 38/40, 19/40 and 30/40 are
   still short of their thresholds. Removing the harness noise makes them measurable; it
   does not make them pass. The archetype-essentialism question from the main report
   (item 2) is unchanged and is now the top of the queue.

### Addendum artifacts

- `.local_data/sweep-g7/results.json` — post-fix per-seed verdicts (40 rows). A second
  sweep run concurrently by another workstream into `.local_data/sweep/results.json`
  came out byte-identical, which is an independent reproduction of the 40/40.
- `tests/simulator/test_demo_clock_bookkeeping.py` — 7 regression tests. The first
  reproduces the exact mechanism on a crafted 3-student, 2-day cohort (one injector
  answering open items with the injection, two hedging students) in 0.14 s; run against
  the pre-fix `_play_day` it reports 3 planted hedges and 2 quarantines.
