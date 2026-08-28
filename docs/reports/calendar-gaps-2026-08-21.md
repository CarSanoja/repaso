# Delivery health, rest-day deferral, and the copy that had to follow (2026-08-21)

**Gate A finally passes: 0/20 seeds yesterday, 20/20 today, and the residual is zero rather than
small.** Twenty held-out seeds (20261100–20261119), five arms, 28 simulated days × 30 students
each — 84,000 student-days through the real pipeline (the shipped daily close, the shipped
`engagement_trigger`, the shipped escalation composer) with simulated students and a scripted
judge, in 806 s, $0. The 566 outage-attributed false alerts that failed gate A yesterday are
gone, every one of the 60 genuine dropouts is still caught — including the one whose silence
*starts* on the first outage day, which is gate D and reads 20/20 — and the pre-fix arm still
fires 1,689 alerts on the same twenty seeds, reproducing yesterday's row for row. The price is
paid in latency: a dropout whose evidence window is swallowed by the outage is now alerted 6
school days after its last response instead of 3, because three of those days carried no evidence
either way.

## Setup

| Item | Value |
|---|---|
| Command | `nice -n 19 python scripts/run_calendar_bench.py --seeds 20 --first-seed 20261100 --workers 3` |
| Runs | 5 arms × 20 seeds × 28 days × 30 students = 84,000 student-days; 2,400 student-weeks per arm |
| Wall clock / cost | 806 s / $0 (offline, scripted doubles, no network, no credentials). A `flat` run costs ~60 s against ~16 s for an overlay run, which has half the practice days. The four declared arms had been run alone an hour earlier, in 724 s, and reproduced every number in this report exactly |
| Fixes under test | `core/harness/calendar.outage_days` (+ `OUTAGE_COLLAPSE_RATIO = 0.2`, `OUTAGE_BASELINE_DAYS = 7`); the quality graph's engagement node (cohort-wide daily totals → outage days → threaded into the mask) and its engagement *and* cohort nodes (skip a family whose own calendar cannot deliver today, checked before any weekly claim is taken); the `engagement_alert` string in `i18n/es.py` and `i18n/en.py` |
| Overlay (reality, identical in every overlay arm) | Sat + Sun rest; Carnaval 2026-09-14/15; Semana-Santa block 2026-09-21…25; outage 2026-09-08…10 where sessions are delivered and nobody answers. 13 of the 28 days are school days: 390 sessions and 753 responses per run |
| Arms | `flat` — no overlay at all, 28 practice days · `on` — overlay, calendar configured **and** delivery-health check live · `off` — overlay, neither (the build that shipped before today; the health helper is stubbed out in this arm) · `health` — overlay, health check only, no calendar · `defer` — overlay, calendar only, health check stubbed. The last two define no gate; they exist to separate the two masks |
| Planted case added today | In the overlay arms the bench shifts **stu17** (one of the three `disengaged` students) by one day so its silence begins on the first outage day, 2026-09-08. Gate D is measured on it. The other two dropouts are untouched |
| Settings deviating from defaults | `holiday_dates` set in the `on` and `defer` arms only. `escalation_min_samples` is 9, the tree's current default |
| Cohort | `simulator/cohort.build_cohort`, unchanged: 30 students, the eight archetypes, matrix (a) in `scripts/README.md` |

### Gates, declared before the first run

The five gates below are coded in `scripts/calendar_report._gates`, which prints its own
verdicts, and were fixed before the sweep started. Gate A's threshold, gate A2, gate B's
threshold and gate C are yesterday's, unchanged. Gate D is new and was written with the fix, not
after seeing it work.

| Gate | Arm | Threshold | Why this number |
|---|---|---|---|
| **A** zero false engagement alerts per run | `on` | ≥ 95 % of seeds | The claim yesterday's fix could not earn: no family doing nothing wrong is told their child stopped practicing. Yesterday: 0/20 |
| **A2** zero *calendar-caused* false alerts per run | `on` | 100 % of seeds | Kept from yesterday so a calendar leak cannot hide inside a residual, and so today's fix cannot be credited with yesterday's win |
| **B** every genuine dropout alerted within 3 **practicable** days of its last response (the script prints this row as `<= 3 scheduled days`, yesterday's wording for the same predicate) | `on` | ≥ 90 % of seeds | Masking must not buy quiet by going blind. "Practicable" — a school day on which the platform was up — is the unit the fixed detector counts, and it is computed from reality, identically in every arm. The school-day and calendar-day latencies are printed beside it so the cost shows rather than hiding in the denominator |
| **C** the pre-fix arm still produces false alerts | `off` | majority of seeds | The control that makes the benchmark falsifiable. It has to switch *both* fixes off: the health check alone also suppresses the calendar gaps (that is what the `health` arm measures), so an `off` arm that kept it would have been clean for the wrong reason and the benchmark would measure nothing |
| **D** the dropout whose silence begins on the first outage day is still caught, within 3 practicable days | `on` | 100 % of seeds | Outage-blindness is the cheap way to pass gate A dishonestly: mask the outage and you stop seeing the child who quit during it. Deterministic by construction — stu17 answers 100 % of the time until it stops — so anything under 100 % is a defect, not variance |

**Attribution rule (yesterday's, with one addition).** Each alert replays the trailing silent run
the detector actually consumed, under that arm's masks: `calendar` if the run contains a rest day
or holiday (structurally impossible with the calendar mask on), else `outage` if it contains an
outage day (structurally impossible with the health check on), else `noise`. The addition: the
gap-type table replays the alert's silence in **plain calendar days** instead, so it still reports
what a family's quiet spell spanned even when the detector counted none of it. In the `off` arm
the two coincide, which is why that column matches yesterday's exactly.

**Seed hygiene.** 20261100–19 is the calendar block, spent yesterday. Today re-measures the same
fixed world with a changed detector; nothing was tuned on it, and both knobs the fix introduces
(0.2 of the trailing median, a 7-day baseline) were fixed by spec before the first execution and
never moved. The smoke test ran on **20261200**, the first seed of the next unspent block,
precisely so the measured block stayed untouched; that seed is now spent.
`docs/reports/calibration-validation-2026-08-20.md` holds the full table.

**One arm was added after the sweep.** `flat`, `on`, `off` and `health` were declared before the
first run; `defer` was added when the results showed the health check accounts for the entire
residual on its own, leaving the rest-day deferral with nothing to remove in the `on` arm. It
defines no gate, moved no threshold, and the four original arms reproduced their numbers exactly
when the sweep was re-run with it.

## Gates vs reality

| Gate | Result | Verdict |
|---|---|---|
| A zero false alerts per run, calendar + health on | 20/20 | **passed** — 0 alerts in 2,400 student-weeks, against 566 yesterday |
| A2 zero calendar-caused false alerts | 20/20 | passed — 0 of 1,191 |
| B dropouts alerted ≤ 3 practicable days | 20/20 | passed — 60/60 at exactly 3 |
| C the pre-fix arm still fires false alerts | 20/20 | passed — every seed dirty, 84.5 per run |
| D the outage-onset dropout still caught | 20/20 | passed — 20/20 at exactly 3 practicable days |

## What each mask removes

False engagement alerts, meaning alerts to a student who is not the `disengaged` archetype. One
row per alert delivered, so a family alerted twice counts twice — a parent counts messages.

| Arm | What the deployment knows | Alerts | Distinct students | Per run | Per 100 student-weeks | calendar | outage | noise |
|---|---|---|---|---|---|---|---|---|
| `flat` | no gaps exist at all | 5 | 5 | 0.2 | **0.2** | 0 | 0 | 5 |
| `off` | neither mask (pre-fix) | 1,689 | 540 | 84.5 | **70.4** | 1,191 | 498 | 0 |
| `defer` | calendar only | 543 | 539 | 27.1 | **22.6** | 0 | 543 | 0 |
| `health` | delivery health only | 0 | 0 | 0.0 | **0.0** | 0 | 0 | 0 |
| `on` | both | **0** | 0 | 0.0 | **0.0** | 0 | 0 | 0 |

The `defer` arm is yesterday's shipped build plus today's rest-day deferral — the copy change is
text and the stu17 plant moves a detection, neither touches a false-alert count — so the pair
566 → 543 is the deferral's contribution measured on its own: **23 packets fewer, and
none at all on a morning the school was shut.** Yesterday 27 alerts went out on Carnaval Monday;
today the close on 09-14 delivers nothing and takes no weekly claim, and two school days later
only 4 of those 27 families are alerted, on Wednesday 09-16. The other 23 are never told anything:
their child practiced before the deferred close came round. Waiting for a day that can deliver
does not merely move a packet, it dissolves five sixths of that batch — which is another way of
saying most of those alerts were wrong when they were sent.

The health check is doing the heavy lifting. 543 of yesterday's 566 residual alerts were outage
silence that no calendar mask can see, and the `health` arm shows the check alone would have
taken the calendar gaps too. Every column of the `on` row is zero — not "small", zero across
2,400 student-weeks.

By gap type — the alert's silence replayed in calendar days, so rows overlap on purpose:

| Gap | `flat` | `off` | `defer` | `health` | `on` |
|---|---|---|---|---|---|
| weekend | 0 | 1,191 | 45 | 0 | 0 |
| Carnaval | 0 | 540 | 4 | 0 | 0 |
| Semana Santa | 0 | 569 | 0 | 0 | 0 |
| outage | 0 | 525 | 543 | 0 | 0 |

And by the day the packet went out — the shape of the harm, not just its size. The
`2026-08-20 on` column is yesterday's shipped build, quoted from the previous report, so the
deferral's effect can be read off one row:

| Fire date | `flat` | `off` | `2026-08-20 on` | `defer` | `health` | `on` | What that day is |
|---|---|---|---|---|---|---|---|
| 2026-09-05 Sat | 0 | 23 | 0 | 0 | 0 | 0 | first weekend, for students who also missed Friday |
| 2026-09-06 Sun | 0 | 18 | 0 | 0 | 0 | 0 | same weekend, one day later |
| 2026-09-07 Mon | 3 | 41 | 0 | 0 | 0 | 0 | three trailing calendar days = Fri + Sat + Sun |
| 2026-09-09 Wed | 0 | 0 | 41 | 41 | 0 | 0 | outage day 2, for students who also missed Monday |
| 2026-09-10 Thu | 2 | 498 | 498 | 498 | 0 | 0 | outage day 3 — school was open and nobody could answer |
| 2026-09-14 Mon | 0 | **540** | **27** | **0** | 0 | 0 | Carnaval: the mask fixed the verdict, the deferral fixed the morning |
| 2026-09-16 Wed | 0 | 0 | 0 | 4 | 0 | 0 | where those 27 went: 4 packets, two school days later |
| 2026-09-21 Mon | 0 | **540** | 0 | 0 | 0 | 0 | Semana Santa: every enrolled family, again |
| 2026-09-28 Mon | 0 | 29 | 0 | 0 | 0 | 0 | back from the break |

## Detection latency for genuine dropouts

Three clocks on the same 60 detections per arm. *Practicable* days are school days on which the
platform was up — what the fixed detector counts and what gate B scores. All three are computed
from reality, so the columns compare across arms.

| Arm | Found | 0 | 1 | 2 | 3 | > 3 | missed | mean school days | mean calendar days |
|---|---|---|---|---|---|---|---|---|---|
| `flat` | 60/60 | 0 | 0 | 0 | 60 | 0 | 0 | 3.0 | 3.0 |
| `off` | 60/60 | **20** | 40 | 0 | 0 | 0 | 0 | 1.7 | 3.0 |
| `defer` | 60/60 | **20** | 40 | 0 | 0 | 0 | 0 | 3.0 | 4.3 |
| `health` | 60/60 | 0 | 0 | 0 | 60 | 0 | 0 | 6.0 | 11.3 |
| `on` | 60/60 | 0 | 0 | 0 | 60 | 0 | 0 | 6.0 | 11.3 |

Nobody is missed anywhere, and the distribution is a spike, not a spread: the trigger needs
exactly three trailing silent countable days and the overlay is deterministic. The interesting
column is the **20 detections at zero practicable days** in `off` and in `defer` — every one of
them stu17, alerted on 2026-09-10 on the strength of three outage days, which is a correct verdict
reached with no evidence at all. Under the fix the same student is alerted on 09-17 after 09-11,
09-16 and 09-17: three days on which it could have practiced and did not.

The 40 pre-outage dropouts (stu15, stu16) last answer on Friday 2026-09-04 and are alerted on
Wednesday 2026-09-16: 3 practicable days, 6 school days, 12 calendar days. Yesterday the same
students were alerted on 09-09, 5 calendar days out. **The outage costs a week of detection
latency on any dropout whose silence it swallows** — that is the real trade this fix makes, and
it is invisible in gate B because gate B counts the days that carried evidence.

## What the delivery-health check masked

Reconstructed by replaying `outage_days` over each run's finished grade log with that arm's
detector calendar. The pipeline computes it inside a rolling 14-day window; the reconstruction is
identical here because the trailing baseline never leaves that window.

| Arm | Days masked per run | weekend | Carnaval | Semana Santa | outage | same set in every seed |
|---|---|---|---|---|---|---|
| `flat` | 0.0 | 0 | 0 | 0 | 0 | yes |
| `off` | check disabled | — | — | — | — | — |
| `defer` | check disabled | — | — | — | — | — |
| `on` | **3.0** | 0 | 0 | 0 | 60 | yes |
| `health` | **18.0** | 160 | 40 | 100 | 60 | yes |

The `on` row is the fix behaving exactly as specified: three days, the three outage days, in all
twenty seeds, and nothing else. The `health` row is the honest complication — with no calendar
configured, the same check masks 18 of 28 days, because a school-wide holiday and a platform
outage look identical from the response log. That is why the `health` arm is as clean as `on`,
and why the `off` control had to switch both fixes off.

## Gates the fixes were not supposed to move

The nine-row ledger from `simulator/verdicts.py`, per arm:

| Verdict row | `flat` | `off` | `defer` | `health` | `on` |
|---|---|---|---|---|---|
| struggle triage reaches every low-ability student | 20/20 | 8/20 | 8/20 | 8/20 | 8/20 |
| struggle triage never fires outside the low-ability group | 13/20 | 13/20 | 13/20 | 13/20 | 13/20 |
| refires wait out the full cooldown | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 |
| engagement alert reaches every disengaged student | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 |
| engagement alert never fires for active students | 15/20 | **0/20** | **0/20** | 20/20 | **20/20** |
| cohort signal only in 4-b, ≤ 1/week | 17/20 | 13/20 | 13/20 | 13/20 | 13/20 |
| every planted injection intercepted | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 |
| every hedged open answer quarantined | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 |
| fast-guess switch fires for exactly the fast guessers | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 |

**160/160 non-engagement seed-rows are identical between `on` and `off`** — the same strong form
as yesterday: not equal totals, equal verdicts seed by seed. The engagement row flips 0/20 → 20/20,
which is the whole point, and the cohort row is unmoved at 13/20 in every overlay arm, so
deferring cohort signals off rest days cost nothing measurable here. Note that the `on` arm now
beats `flat` on the engagement row, 20/20 against 15/20: the flat world has 28 practice days and
therefore 28 chances for response-rate randomness to produce three silent days in a row.

## Honest read

1. **Gate A passes, and the fix that earned it is the health check, not the deferral.** The
   `health` arm — no calendar configured at all — is as clean as `on`. In this world the calendar
   mask is redundant, and saying otherwise would be taking credit twice for one idea.
2. **That redundancy is an artifact of the overlay, and the artifact flatters the health check.**
   Rest days here are uniform across the whole cohort (`_play_day` uses one overlay for
   everybody), so a school-wide holiday is indistinguishable from an outage in the response log.
   The check only fires when more than 80 % of the usual daily volume disappears; a single
   family's trip — the case the per-family `rest_weekdays` mask exists for — does not move it at
   all. Neither does a section-scoped outage, which is the version the adversarial review
   actually specified. Both remain untested.
3. **The check cannot tell "our platform was down" from "the whole school stopped".** The 18
   masked days in the `health` arm are that sentence with a number on it. Whether that is a
   feature or a blindness is a product decision nobody has made: today it means an unconfigured
   school is protected from false alarms, and it equally means nobody is told when an entire
   cohort quits at once.
4. **The latency cost is real and larger than yesterday's.** 3 practicable days is 6 school days
   and 11.3 calendar days on average; on the two pre-outage dropouts it is 12 calendar days
   between the last response and the packet, against 5 yesterday. A three-day outage buys a
   week of blindness on genuine dropouts. Gate B does not see it because gate B counts days that
   carried evidence — which is the right unit for the detector and the wrong unit for a parent.
5. **The copy sign-off is only half honest.** ES now reads "{days} días de clase sin practicar"
   and EN "{days} school days without practicing", which is closer to the truth than "días" was.
   But the number is school days *on which the platform was up*: on 2026-09-16 a parent is told
   "3 días de clase" when six school days have passed since their child last practiced. The
   string is more accurate and still not exactly true, and no copy exists for "we were down".
   The change also broke one assertion outside the files this work owns —
   `tests/agents/test_closure.py` pinned the old sentence verbatim — which is the cheapest
   possible reminder that shipped copy has readers on both sides of the wire.
6. **The rest-day deferral bought 23 packets out of 566, and its real claim is not a count.**
   The `defer` arm exists because the `on` arm cannot show it: with the health check in place
   there was nothing left for it to defer. Against yesterday's build it removes the 27
   Carnaval-morning packets and re-delivers 4 of them on the next school morning — the other 23
   families had practiced by then and were never told anything. What it guarantees is
   categorical rather than statistical: **no engagement or cohort packet can be delivered on a
   day the family's own calendar has shut**, and the weekly claim is not spent on a close that
   cannot deliver. The unit tests are the evidence for the claim half, because a burned claim
   would show up as silence for a whole week and no bench arm distinguishes that from a fix.
7. **A cohort of one is a hole.** The check masks a day only when the cohort's total collapses,
   so with N students each answering once a day, one student's silence trips it only at N = 1
   (measured directly: N = 1 flags, N = 2, 3, 5, 30 do not). A single-family deployment would
   therefore never receive an engagement alert. The unit tests seed three answering peers for
   exactly this reason, which is itself the evidence that the check is a cohort instrument.
8. **The cohort k-floor now counts only families that can deliver today.** Skipping a resting
   family in the cohort node also removes its failure from the `cohort_min_families` count and
   its family from the fan-out. With a uniform calendar that is all-or-nothing and cost nothing
   (13/20, unchanged). With per-family rest days a section could drop below the floor because one
   family rests on a Wednesday. Untested, and worth a test before per-family calendars ship.
9. **Nothing records what was masked.** The table above is a reconstruction from the finished
   grade log, not an observation: no telemetry event says "2026-09-08 masked, cohort total 0
   against a median of 58". An operator asking "why did we not alert this family" has no way to
   find out. That is the next small change, and it is cheaper than anything else in this list.
10. **The engagement node now reads the whole grade log twice per close.** `_all_grades` for the
    cohort totals, then a per-student read for every student. At 30 students that is a 16-second
    run; at 3,000 it is a nightly full scan of everything ever graded. The cohort total wants to
    be a maintained daily aggregate before this ships.
11. **The pre-fix arm reproduces yesterday's numbers exactly** — 1,689 alerts, 540 distinct
    students, the same seven fire dates with the same counts, 1,191 calendar and 498 outage —
    even though the harness now shifts stu17's dropout day. That is the determinism claim being
    cashed rather than asserted, and it is what makes "566 → 0" a comparison rather than two
    unrelated runs.
12. **The struggle rows are still broken under the overlay and today's work did not touch them.**
    Recall 20/20 → 8/20 and the cohort row 17/20 → 13/20 in every overlay arm, unchanged from
    yesterday: 13 practice days in 28 calendar days is half the evidence
    `escalation_min_samples = 9` was calibrated against. That remains the largest open item in
    this benchmark and it is not a calendar bug.
13. **The stylizations that flattered yesterday still flatter today.** Universal outage, uniform
    rest days, one flat holiday list, 28 days against a 14-day signal window, and a bench where
    the only silence that matters is total. A recess longer than the window is still untested.

## Artifacts

- `.local_data/calendar/results.json` — 100 rows (5 arms × 20 seeds): scheduled days, sessions,
  responses, every engagement alert with fire date, cause, gap types and silent-day count, the
  dropout detections with latency in practicable / school / calendar days, the days the health
  check masked, and the nine ledger verdicts.
- `.local_data/calendar/<arm>-<seed>/` — 100 full local backends, one per run.
- `tests/harness/test_calendar.py` (23 cases, 8 of them on `outage_days`: collapse detected,
  a 0.5 dip refused, no baseline at the start, the recovery day counting again, a five-day outage
  that does not drag its own baseline down, closed days never flagged, and both knobs) and
  `tests/orchestration/test_scheduled_engagement.py` (10 cases, including the outage control pair
  — the same three silent days alarm when the rest of the cohort kept answering — the
  outage-onset dropout, and the two deferral tests that prove the weekly claim survives a holiday
  close). Full suite **706 passed**: 675 before this work, +13 from those two files, and +19 from
  `tests/benchmarks/test_school_week_audit.py`, which landed in the tree from unrelated work
  while this ran.
- Case matrix (d) in `scripts/README.md` — the overlay's cases and what would falsify each.
