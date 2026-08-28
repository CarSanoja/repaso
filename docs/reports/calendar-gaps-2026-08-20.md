# Calendar-gap robustness — silence counted in school days (2026-08-20)

**The calendar false alarm is gone. The outage false alarm is not, and the pre-registered gate
fails on it.** Twenty held-out seeds (20261100–20261119), three arms, 28 simulated days × 30
students each — 50,400 student-days through the real pipeline (the shipped daily close, the
shipped `engagement_trigger`, the shipped escalation composer) with simulated students and a
scripted judge, in 614 s, $0. With the school calendar configured, calendar-caused false
engagement alerts go from **1,191 to 0** — 49.6 to 0.0 per 100 student-weeks — and all 60
genuine dropouts are still caught, at exactly 3 scheduled days each. Gate A still reads 0/20,
because a 3-day platform outage is silence on days the school was open, the mask was never
designed to hide it, and 566 alerts remain: every one of them outage-attributed.

## Setup

| Item | Value |
|---|---|
| Command | `nice -n 19 python scripts/run_calendar_bench.py --seeds 20 --first-seed 20261100 --workers 3` |
| Runs | 3 arms × 20 seeds × 28 days × 30 students = 50,400 student-days; 2,400 student-weeks per arm |
| Wall clock / cost | 614 s / $0 (offline, scripted doubles; a second sweep held cores on the same machine — the same run measured 566 s an hour earlier with identical numbers) |
| Fix under test | `core/harness/calendar.py` (`is_scheduled`, `mask_to_scheduled`), `response_graph.scheduled_counts`, the quality graph's engagement node, `family.rest_weekdays`, `settings.holiday_dates` |
| Overlay (reality, identical in the `on` and `off` arms) | Sat + Sun rest; Carnaval 2026-09-14/15; Semana-Santa block 2026-09-21…25; outage 2026-09-08…10 where sessions are delivered and nobody answers. 13 of the 28 days are school days: 390 sessions and ~750 responses per run |
| Arms | `flat` — no overlay at all, 28 practice days, the shape every earlier report measured · `on` — overlay, calendar configured on every family and in `Settings` · `off` — overlay, calendar not configured, which is exactly what shipped before today |
| Settings deviating from defaults | `holiday_dates` set in the `on` arm only. `escalation_min_samples` is 9, the tree's current default |
| Cohort | `simulator/cohort.build_cohort`, unchanged: 30 students, the eight archetypes, matrix (a) in `scripts/README.md` |

### Gates, declared before the first run

The four gates and the attribution rule below are coded into `scripts/run_calendar_bench.py`,
which prints its own verdicts; they were fixed before the first 20-seed run, so no threshold
could be chosen after seeing a number.

| Gate | Arm | Threshold | Why this number |
|---|---|---|---|
| **A** zero false engagement alerts per run | `on` | ≥ 95 % of seeds | The claim the fix is supposed to earn: "zero false alerts per 100 student-weeks" |
| **A2** zero *calendar-caused* false alerts per run | `on` | 100 % of seeds | The claim the fix actually makes. Split out so a residual from some other silence cannot be smuggled in as a calendar win, and so a calendar leak cannot hide inside a large residual |
| **B** every genuine dropout alerted within 3 **scheduled** days of its last response | `on` | ≥ 90 % of seeds | Masking must not buy quiet by going blind. Latency is counted in school days in every arm, because reality has the same rest days in all of them |
| **C** masking OFF still produces false alerts | `off` | majority of seeds | The control that makes the benchmark falsifiable. If the unmasked arm were clean too, the benchmark would be measuring nothing |

**Attribution rule (declared with the gates).** For each alert, replay the trailing silent run
the detector actually consumed, then label it: `calendar` if that run contains a rest day or a
holiday — structurally impossible with the mask on, which is the point — else `outage` if it
contains an outage day, else `noise`. Causes are exclusive and ordered; the gap-type table below
counts an alert once per gap kind its silent run touches, so its rows overlap on purpose.

**Held-out, with one asterisk.** Seed 20261100 was run once as a smoke test before the sweep, so
it is not strictly held out. Dropping it moves nothing: A 0/19, A2 19/19, B 19/19, C 19/19. The
`flat` control arm and the gap-type split were added after the first two-arm run as diagnostics;
they define no gate and changed no threshold, and re-running the whole thing reproduced the
two-arm numbers exactly (566 / 1,689 alerts, same fire dates, same 60 detections).

## Gates vs reality

| Gate | Result | Verdict |
|---|---|---|
| A zero false alerts per run, masking on | 0/20 | **FAILED** — 28.3 alerts per run remain, all from the outage |
| A2 zero calendar-caused false alerts | 20/20 | passed — 0 of 1,191 |
| B dropouts alerted ≤ 3 scheduled days | 20/20 | passed — 60/60 at exactly 3 |
| C masking off still fires false alerts | 20/20 | passed — every seed, 84.5 per run |

## Masking ON vs OFF

False engagement alerts, meaning alerts to a student who is not the `disengaged` archetype.
One row per alert delivered, so a family alerted twice counts twice — a parent counts messages.

| Arm | Alerts | Distinct students | Per run | Per 100 student-weeks | calendar | outage | noise |
|---|---|---|---|---|---|---|---|
| `flat` (no gaps at all) | 5 | 5 | 0.2 | **0.2** | 0 | 0 | 5 |
| `on` (calendar configured) | 566 | 539 | 28.3 | **23.6** | **0** | 566 | 0 |
| `off` (calendar not configured) | 1,689 | 540 | 84.5 | **70.4** | **1,191** | 498 | 0 |

Masking removes 1,123 of 1,689 alerts — 66.5 % — and takes the calendar bucket to zero. The
`flat` row is the irreducible floor: with no gaps in the world at all, response-rate randomness
alone still produces 0.2 false alerts per 100 student-weeks.

By gap type (an alert can touch several, so rows overlap):

| Gap | `flat` | `on` | `off` | `off` per 100 student-weeks |
|---|---|---|---|---|
| weekend | 0 | 0 | 1,191 | 49.6 |
| Carnaval | 0 | 0 | 540 | 22.5 |
| Semana Santa | 0 | 0 | 569 | 23.7 |
| outage | 0 | 566 | 525 | 21.9 |

And by the day the packet went out — the shape of the harm, not just its size:

| Fire date | `flat` | `on` | `off` | What that day is |
|---|---|---|---|---|
| 2026-09-05 Sat | 0 | 0 | 23 | first weekend, for students who also missed Friday |
| 2026-09-06 Sun | 0 | 0 | 18 | same weekend, one day later |
| 2026-09-07 Mon | 3 | 0 | 41 | three trailing calendar days = Fri + Sat + Sun |
| 2026-09-09 Wed | 0 | 41 | 0 | outage day 2, for students who also missed Monday |
| 2026-09-10 Thu | 2 | 498 | 498 | outage day 3 — identical in both arms |
| 2026-09-14 Mon | 0 | 27 | **540** | Carnaval: **every** non-disengaged student in **every** seed |
| 2026-09-21 Mon | 0 | 0 | **540** | Semana Santa: the same, again |
| 2026-09-28 Mon | 0 | 0 | 29 | back from the break |

540 is 27 non-disengaged students × 20 seeds — the whole cohort, twice, on two mornings. That is
the pilot's first-week catastrophe the adversarial review predicted, reproduced end to end. With
the calendar configured those two mornings are silent, and the 09-10 column is untouched because
the mask has nothing to say about a day school was open.

The 566 remaining alerts break into 41 on 09-09 (students who had also missed Monday 09-07), 498
on 09-10 (the third outage day), and 27 on 09-14 — repeat fires in the next ISO week for students
who also missed 09-11, the day service came back. 539 of 540 student-runs get at least one.

## Detection latency for genuine dropouts

The three `disengaged` students stop at `dropout_day = 6` = 2026-09-07, last response 09-04.
Latency is counted in school days in every arm, because the school is shut on the same days in
all of them.

| Arm | Dropouts found | 1 day | 2 days | 3 days | > 3 days | missed |
|---|---|---|---|---|---|---|
| `flat` | 60/60 | 0 | 0 | 60 | 0 | 0 |
| `on` | 60/60 | 0 | 0 | 60 | 0 | 0 |
| `off` | 60/60 | 60 | 0 | 0 | 0 | 0 |

Nobody is missed in any arm, and the distribution is a spike, not a spread — the trigger needs
exactly three trailing silent days and the overlay is deterministic. **Masking costs two calendar
days.** Masked, the alert lands 2026-09-09, three school days and five calendar days after the
last response. Unmasked it lands 09-07, after three calendar days, one of which was a school day.
The unmasked arm is faster on real dropouts for the same reason it is wrong on holidays: it
counts the weekend.

## Gates the overlay was not supposed to move

The nine-row ledger from `simulator/verdicts.py`, per arm:

| Verdict row | `flat` | `on` | `off` |
|---|---|---|---|
| struggle triage reaches every low-ability student | 20/20 | 8/20 | 8/20 |
| struggle triage never fires outside the low-ability group | 13/20 | 13/20 | 13/20 |
| refires wait out the full cooldown | 20/20 | 20/20 | 20/20 |
| engagement alert reaches every disengaged student | 20/20 | 20/20 | 20/20 |
| engagement alert never fires for active students | 15/20 | 0/20 | 0/20 |
| cohort signal only in 4-b, ≤ 1/week | 17/20 | 13/20 | 13/20 |
| every planted injection intercepted | 20/20 | 20/20 | 20/20 |
| every hedged open answer quarantined | 20/20 | 20/20 | 20/20 |
| fast-guess switch fires for exactly the fast guessers | 20/20 | 20/20 | 20/20 |

**Masking changes nothing outside the engagement path: 160/160 seed-rows identical between `on`
and `off`** across the eight non-engagement rows. That is the strong form of "unaffected" — not
equal totals, equal verdicts seed by seed.

The overlay itself is a different story, and the `flat` column is why it was added. Struggle
recall falls 20/20 → 8/20 and the cohort row 17/20 → 13/20 when the calendar goes in, identically
in both masked arms. The cause is practice volume, not masking: 28 calendar days with a school
calendar contain 13 practice days, against 28 without one, and `escalation_min_samples = 9` needs
attempts before a struggling child can be triaged at all.

## Honest read

1. **Gate A failed, and the failure is entirely the outage.** Not "mostly" — 566 of 566
   remaining alerts are outage-attributed and the calendar bucket is structurally empty rather
   than merely small. The fix does what it claims and nothing more. Reporting A as passed by
   quietly dropping the outage from the overlay was available and would have been dishonest.
2. **The control is what makes any of this a measurement.** Same world, same seeds, same
   students; the only difference is whether the deployment was told the school calendar. 1,689
   alerts against 566, and two mornings where every enrolled family in every seed is told their
   child stopped practicing. Without the `off` arm, "0 calendar alerts" would be a claim about a
   benchmark that cannot fail.
3. **Masking costs two calendar days of dropout latency, on every single dropout.** 60/60 at
   three school days is the gate passing; it is also two days later than the unmasked arm on a
   child who really did stop. For a 3-day threshold on a 5-day school week that is the trade the
   fix makes, and it should be re-checked against a longer window before the pilot.
4. **The outage residual is a different bug with a known shape.** Silence when the platform,
   not the family, went quiet is a delivery-health question: the engagement node should require
   evidence that the system was reachable before it blames a family. A cohort-wide response-rate
   collapse is trivially detectable — 750 responses on a normal day, 0 on 09-08 — and no such
   check exists. That is the next action, and it is not this fix's job.
5. **The overlay is stylized, and every simplification flatters the result.** Rest days are
   uniform across families (`_play_day` uses one overlay for the whole cohort), so a
   single-family trip — the case T2 also names — is untested. The outage is modeled as universal
   silence, where T2 specified one section; universal silence is the easiest version to detect
   and the easiest to attribute. Holidays are a flat date list with no per-school variation. 28
   days is not a term, and the two-week `SIGNAL_WINDOW_DAYS` means a break longer than the window
   is untested here: Semana Santa's 9 days fit inside it, a month-long recess would not.
6. **The struggle and cohort rows dropping under the overlay is a real finding that this fix
   neither caused nor fixes.** Evidence accumulates at half the rate the 14-day sweeps assumed
   once weekends exist, so the struggle detector needs roughly twice the calendar time to reach
   the same confidence. Every earlier report's recall number was measured on a cohort that
   practiced seven days a week. That deserves its own pass at `escalation_min_samples`.
7. **The alert text now counts school days.** `engagement_alert` renders "lleva 3 días sin
   practicar" on a day when five calendar days have passed. It is arguably the more useful number
   for a parent, but it is a semantic change to shipped copy that no one signed off on, and the
   ES/EN strings were not touched.
8. **A packet can still land on a rest day.** The daily close runs every day, so 27 of the
   remaining alerts went out on Carnaval Monday. The mask fixes the verdict, not the moment of
   delivery; holding non-urgent packets to the next school morning is a separate, small change.
9. **The response path still counts calendar days, deliberately.** `build_signals` reads
   `daily_counts`, but that path only executes when a child has just answered and the grade is
   already in the log, so its trailing silence is zero by construction and its engagement signal
   can never fire. Changing it would have been churn presented as safety.

## Artifacts

- `.local_data/calendar/results.json` — 60 rows (3 arms × 20 seeds): scheduled days, sessions,
  responses, every engagement alert with fire date, cause, gap types and silent-day count, the
  dropout detections with latency, and the nine ledger verdicts.
- `.local_data/calendar/<arm>-<seed>/` — 60 full local backends, one per run.
- `tests/harness/test_calendar.py` (15 cases) and `tests/orchestration/test_scheduled_engagement.py`
  (6 cases) — the unit-level version of the same claim, including the control: the same silence
  that stays quiet with a calendar configured fires an alert without one. Two more in
  `tests/simulator/test_demo_clock_bookkeeping.py` hold the overlay's accounting honest — a rest
  day or a holiday starts no session, takes no answer, and leaves `sessions_delivered` at
  `scheduled_days × students`. Full suite 675 passed.
- Case matrix (d) in `scripts/README.md` — the overlay's cases, and what would falsify each.
