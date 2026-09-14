# Episode experience: recording and verification

The user operates Telegram. The observer reads AWS and does not send messages.
The episode interface was implemented and verified on September 14, 2026.

## Open the experience

Live observer: <http://127.0.0.1:8767/judge/memory/>. Local access code: `REPASO-VIEW`.
Keep the access code and personal identifiers out of the public recording.
The entry view organizes evidence by learner and topic. Open an episode to inspect
three synchronized columns: retained conversation, agent activity and memory,
and learning evidence for the topic.

A conversation reconstructed from retained records is not a complete Telegram
archive. A saved learner note may be an excerpt or have its text cleared after
session close. Full agent messages require a verified link to a delivery record.
Missing traces must stay visibly missing; a matching time alone is not proof.

## The short scene

1. Show the topic card: who needs help, what topic, and how much evidence exists.
2. Open the latest explanation episode. Keep Telegram beside the observer or
   first show Telegram, then expand the episode interface for legibility.
3. Select the learner's request for another example. Follow the same episode
   across all three columns: previous context loaded, new approach stored,
   actual delivered explanation, unchanged assessed count.
4. In Replay, move between the first and second explanations. Explicitly call
   this a reconstruction of recorded activity. Latest aggregate metrics must not
   be presented as a historical snapshot at the selected replay instant.
5. Return to Live before sending a new Telegram message. After responding to an
   offered question, inspect its recorded result and any actual mastery update.
6. Reload and reopen the episode to demonstrate persisted evidence.

Suggested narration:

> Here is the student's request. Here is the approach Repaso already tried.
> When they ask again, the agent retrieves that memory and offers a different
> explanation. We can follow the reply all the way back to its recorded evidence.
> Asking for help leaves the assessment count unchanged. An actual answer is
> what adds learning evidence.

## What the metrics mean

- Assessed answers: effective evaluated outcomes, excluding held or unresolved
  results in the topic analysis.
- Correct answers: correct evaluated outcomes, not help requests.
- Distinct assessed questions: exact content groups; IDs and option order do not
  make duplicate content new. This does not establish semantic uniqueness.
- Difficulty coverage: observed results at each item's stored difficulty level.
  Do not call those values a measured progression without longitudinal evidence.
- Mastery estimate: the application's stored weighted accuracy and policy level.
  It is an estimate of observed practice, not a validated claim of learning gain.
- Explanations remembered: successful retained approaches, not every help request.
- Descriptive summary: a factual reading of those stored metrics. No invented
  diagnosis, causal improvement claim or hidden model thought process.

The real baseline from the confirmed Telegram trial is 3 correct assessments
on repeated content, with 2 different retained explanation approaches. The two
explanations verify adaptation and memory retrieval. They do not prove improved
student understanding. The next assessment must be read from AWS when it happens.

## Running the observer

```bash
.venv/bin/python scripts/run_memory_observer.py \
  --family-id ID_DE_LA_FAMILIA_AUTORIZADA \
  --profile quanta --region us-east-1 --port 8767 --history-minutes 1440
```

The initial log lookup covers 24 hours, with bounded event retention; subsequent
reads revisit the last 15 minutes for late-arriving logs. The interface can still
show retained state when some supporting traces are outside the available window.
The separate local rehearsal uses scripted model replies and local delivery:

```bash
.venv/bin/python scripts/run_memory_observer.py --rehearsal --port 8870
```

## Verification

- Full regression suite: **2129 passed, 66 skipped**, 101.72 seconds, before the
  final assessment projection addition. After that addition: **46 API tests passed**.
- Browser rehearsal: correct/incorrect access code, topic map to episode, two help
  requests with linked replies and prior-context retrieval, answer producing an
  assessment episode, Live/Replay and scrubber, playback, persistence after reload,
  error recovery and disconnect. No JavaScript errors.
- Visual review: desktop 1440 px, split-screen width 900 px and mobile 390 px;
  no horizontal overflow. The selected chat turn automatically comes into view,
  and both previous and newly saved approaches are visible in the central panel.
- Actual AWS observer: six existing episodes reconstructed (three assessments,
  failed explanation, two successful explanations); latest turn links the actual
  paper-folding reply to one prior cake approach and confirmed transport events.
  Counters remain **3 assessments / 2 remembered explanations**.
- Source checks: Ruff, JavaScript syntax and whitespace checks passed.
- The current observer and separate fresh rehearsal are running on ports 8767
  and 8870 respectively. No AgentCore runtime deployment was required for this UI.

The [verified screenshot](assets/episode-observer-rehearsal.png) shows a synthetic
rehearsal with two explanations and zero assessments. It is not an AWS screenshot.

For the real recording, click **Open learning episode** on the fractions card.
The most recent explanation is selected automatically. Click **Replay** and move
between the two successful explanations (currently turns 05 and 06). Return to
**Live** before demonstrating a new message. Do not use a historical replay to
imply the bot is receiving new input.

An open study sitting can expire after inactivity. Before asking the user for a
new real answer, check that the current question is still actionable; recorded
replay remains available independently of whether a practice is still open.

## Family and student evolution

The School Community Memory dashboard adds a family overview and filters for a
learner and topic. Daily activity and cumulative evidence use effective assessment
records plus retained help notes. Select a date to inspect its recorded counts.
The display offers 14- and 30-day windows in the family's timezone; cumulative
counts include any earlier assessment baseline.

Use this opening for the final video: family dashboard → learner → fractions →
recorded day → open learning episode → compare the two explanation approaches.
The dashboard's next-review dates come from stored spaced-review records; a due
date is not proof of a future Telegram delivery. Adult choices are shown from
recorded decisions, scoped to the selected learner/topic when that association
exists. The selected family's data is not an aggregate across a real school.

Only one day of real activity is currently available. Show that day explicitly;
do not suggest there is a measured longitudinal improvement curve. Help history
is limited by retention and is not a lifetime count. The interface shows growth
of recorded evidence, not a reconstructed historical mastery score.

The episode columns are expanded vertically, with larger text for the chat and
memory comparison. The three views remain synchronized and the dashboard is
hidden while an episode is open.

Dashboard validation on September 14:

- **49 API tests passed** after adding the evolution projection, including
  replacement grades, held answers, timezone boundaries, learner isolation,
  repeated content and the pre-window cumulative baseline.
- Real AWS dashboard: 3 evaluated answers, 1 distinct question content, 3 retained
  help requests, 2 retained approaches, 1 active day. Stored review date: September
  15. Duplicate review entries for the same question/date are grouped visually.
- Chrome on AWS: dashboard → selected-day episode worked; no JavaScript errors
  or horizontal overflow. At 1440 px width the episode container measured about
  938 px high, with 14 px chat text and larger approach text.
- Source checks passed: Ruff, JavaScript syntax and whitespace checks.

The frontend scope for the recording is closed. Submission handoff still requires
public code and video links and a completed Devpost form; see the updated
[release record](release-checklist.md). The local observer URL is not public.

Final synthetic browser review also passed at 1440, 900 and 390 px, including a
second learner with no activity, family/topic filtering, selected-day replay and
no cross-learner totals. Verified screenshots:
[family dashboard](assets/family-dashboard-rehearsal.png) and
[taller episode view](assets/episode-observer-rehearsal.png).
The dashboard screenshot shows controlled next-day rehearsal state; the episode
screenshot shows two retained help approaches and zero evaluated answers.
