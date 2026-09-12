# Judging Repaso

Repaso turns a photograph of a printed fourth-grade math page into a short daily
practice that arrives in the parent's Telegram chat at an agreed time. Between
messages it does the work a parent would otherwise repeat every evening: it
reviews the material, keeps a practice bank scoped to that one family, grades
answers, adjusts what comes next, and refuses to grade an answer it is not sure
about. When it is unsure, or when difficulty persists, it stops and hands the
adult a decision with the evidence attached — and the next session shows what
that decision changed.

## Look at this first

The same family, the same page, the same nine reviewed answers, one adult
decision — and two different next mornings. These are the last two rows of the
two runs in [the local path](#the-local-path) below, verbatim:

```
the chosen action is resolved                                        teacher_note             teacher_note  as expected
the next scheduled practice reflects the plan                                   3                        3  as expected
```

```
the chosen action is resolved                                         reduce_load              reduce_load  as expected
the next scheduled practice reflects the plan                                   1                        1  as expected
```

Three questions tomorrow, or one. A button that only acknowledges the tap is the
common failure in this category; the check that the plan actually changed is the
one worth spending your first minute on.

## Is there a hosted demo?

| | Value at this commit |
| --- | --- |
| Judge URL | not published |
| Judge code | not issued |

Nothing in this repository has ever been deployed. `deploy/README.md` is the
procedure and it marks which of its commands were executed read-only against the
authorized account and which were deliberately not run. If the two cells above
are filled in, open the URL, enter the code, and skip to step 3 of the path
below. If they still read *not published*, the local path gets you the same
screen — the same code, the same page, the same assertions — in about three
minutes.

## The five-minute path

1. Get the judge page on screen: the hosted URL if the table above names one,
   otherwise `python scripts/run_judge_demo.py` from the local path below.
2. Enter the code `REPASO-DEMO` and press **a note for the teacher**. The run
   takes a couple of seconds and ends with 24 of 24 checks green.
3. Walk the seven stages: the material, the scheduled delivery, an uncertain
   answer, the adult's review, persistent difficulty, the adult's choice, the
   next practice. The family conversation is Spanish; the navigation is English.
4. Run it again with **less practice tomorrow** and compare stage seven. That is
   the comparison in *Look at this first*.
5. Open [the evidence register](../evidence/README.md) and read its *Claim
   boundaries* section. It is the shortest honest summary of what this project
   has and has not shown.

Everything in steps 2 to 4 is a replay: real orchestration code, real storage,
real scheduling and grading rules, and the first day's model answers played back
from a recording made against Amazon Bedrock on September 12, 2026. The days
after it are authored. The judge endpoint says so in its own response body
(`"origin": "recorded replay"`, `"live_inference": false`), and the terminal run
prints what that recording measured above the table. A replay reaches no network
and spends nothing.

## The local path

No AWS account, no Telegram token, no keys, no Docker. Python 3.12 or newer, named
on the command line: a bare `python3` is 3.9 on macOS, and the install under it
fails with a message about a missing `setup.py` that never mentions the version.
Any `python3.12`, `python3.13` or newer works in its place.

```bash
git clone <repository url> repaso && cd repaso
python3.12 -m venv .venv
source .venv/bin/activate
pip install -c requirements.lock -e ".[dev]"
```

The install is pinned by `requirements.lock` and ends with a line naming every
package it placed, `repaso-0.1.0` last **[run]**:

```
Successfully built repaso
Installing collected packages: py-partiql-parser, jsonpath_ng, xmltodict, wrapt, ... strands-agents, moto, repaso
```

Then the browser experience:

```bash
python scripts/run_judge_demo.py
```

It prints its own address and stays in the foreground **[run]**:

```
Judge experience: http://127.0.0.1:8766/judge/ · code: REPASO-DEMO
INFO:     Started server process [21992]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8766 (Press CTRL+C to quit)
```

Open **http://127.0.0.1:8766/judge/** and enter **REPASO-DEMO**. The state lives
in a temporary directory that is deleted when you stop the server; no family
data, no credentials and no paid model are reachable from those controls.

The same journey runs in the terminal, which is what to use if you want the
assertions rather than the screens. Choose an empty output directory **[run]**:

```bash
python scripts/run_demo_scenario.py --data-dir .local_data/demo-note  --decision teacher_note --report .local_data/demo-note.json
python scripts/run_demo_scenario.py --data-dir .local_data/demo-light --decision reduce_load  --report .local_data/demo-light.json
```

```
cost: 34,697 input + 6,204 output tokens and $0.1649 over 31 recorded model calls
The model outputs are replayed from a recording made on 2026-09-12 in us-east-1, against 3 model ids,
on top of commit a3e382f835a7: the tokens and dollars above are what that one recording measured.
This replay reached no network and spent nothing, and it is not evidence that the models
would answer this way again.
one family, four labeled school days, simulated in 0.5s into .local_data/demo-note

beat                                                                     expected                   actual  verdict
enrolment ends with the family enrolled                                  enrolled                 enrolled  as expected
a name that looks real is refused as an alias                             refused                  refused  as expected
the notebook photo becomes practice                                      material                 material  as expected
questions written from the page                                                 6                        6  as expected
questions that survived review                                                  6                        6  as expected
the capsule carries the day's three questions                                   3                        3  as expected
the answer the grader would not sign reaches the parent                   one tap                  one tap  as expected
the parent's tap settles it as wrong                                     rejected                 rejected  as expected
the guide's worked example is caught                                 all_rejected             all_rejected  as expected
nothing from the guide reaches the child                                        0                        0  as expected
```

The teacher-note run prints 24 beats, the reduce-load run 23; both end with
`the complete journey has no runtime failures  0  0  as expected`.

## For a skeptical judge

Each row is a command you can run yourself and the number it prints. The three
gates take about ninety seconds together; the clock takes about seven minutes.

| Command | What it printed here **[run]** | Artifact |
| --- | --- | --- |
| `REPASO_LOCAL_MODE=true pytest -q` | `1642 passed, 56 skipped in 77.74s` | — |
| `ruff check .` | `All checks passed!` | — |
| `python scripts/check_repo_hygiene.py` | `repo hygiene: 549 tracked files, 1264 historical blobs on this branch, no findings` | — |
| `python scripts/run_demo_scenario.py --decision teacher_note` | 24 of 24 beats as expected | [journey](../evidence/journey-teacher-note.json) |
| `python scripts/run_demo_scenario.py --decision reduce_load` | 23 of 23 beats as expected | [journey](../evidence/journey-reduce-load.json) |
| `python scripts/run_demo_clock.py --days 14 --seed 20260901` | `420 student-days`, `responses graded: 1037`, nine gates as expected | [clock](../evidence/clock-14-days.json) |
| `python scripts/run_answer_evaluation.py` | `"cases": 60, "predictions": 0, "quality_claim_allowed": false` | [validation](../evidence/answer-evaluation-validation.json) |

The 83 skips are the live tier — 56 tests in `tests/live`, off unless you hand
it AWS credentials and a budget — and 27 skips standing in for the
infrastructure tests that read synthesized CloudFormation and need the CDK
libraries. Those 27 are not 27 tests: most of `tests/infra` is never collected
without `aws_cdk`, so `pip install -c requirements.lock -e ".[deploy]"` turns
them into the 124 tests that directory really holds, and the suite then reads
`1642 passed, 56 skipped` — 1518 plus 124, and 83 minus the 27 that stopped
being skips. The hygiene gate also counts every blob reachable
from this branch, which is why it reports a second number the September figures
did not. The suite figure in `docs/evidence/verification-2026-09-06.json` is
`1169` because it was recorded on September 6 against an earlier tree.

`run_answer_evaluation.py` is the one worth reading the output of. It has a
60-example answer set and zero independent labels, and it refuses to turn the
author's own proposed labels into an agreement score: `quality_claim_allowed`
stays `false` and every agreement figure stays `null`. Empty data does not
become perfect accuracy.

## Measured, prepared, and not done

| Claim | State |
| --- | --- |
| Both adult decisions change the next session | Measured, locally, on authored model answers |
| Transport recovers across retries and duplicate events | Measured under Moto with the AgentCore and Telegram boundaries substituted |
| Fourteen days of continuity hold under nine scenario gates | Measured on 30 synthetic students |
| A new printed Spanish page is recognized outside the cassette | Measured: one real Amazon Textract call, confidence 0.9957 |
| Every configured model answers and fills its schema | Measured on 2026-09-12: 27 of 27 calls parsed, $0.1444 |
| Six CloudFormation stacks and two ARM64 images build | Prepared: they synthesize and the containers start and serve; nothing is deployed |
| Model grading quality | Not done. Kit prepared, labels deliberately blank |
| Benefit to a real family | Not done. Three-day observation protocol prepared, no participants |

The single figure a judge should not read past: **no cloud deployment and no
real family exist.** Every number above comes from this machine or from a
read-only call to a service.

## Where the failures are published

- [Claim boundaries](../evidence/README.md#claim-boundaries) — the register's
  own list of what its rows do not establish, including the ten transport runs
  that are *not* ten deployed journeys.
- [The tests that changed the product](article-3-evidence.md) — the features
  whose descriptions turned out to be wrong: a button that acknowledged instead
  of sending, a rejected human review that never became an incorrect outcome, a
  deletion that left bytes behind.
- [The live tier](../../tests/live/README.md) — calls are never retried, because
  a retry repairs exactly the failure that tier exists to find; a failed call is
  recorded and the run continues.
- [The deployment runbook](../../deploy/README.md) — every command marked `[run]`
  or `[unverified]`, and a teardown section about a retained KMS key that nothing
  reports.
- The at-least-once boundary: Telegram `sendMessage` has no idempotency key. If
  it accepts a message and the acknowledgment is lost, a retry can duplicate it.
  Idempotent learning effects and exactly-once visible delivery are different
  properties and only the first is claimed.

## If you want to go deeper

[How it works](../product/how-it-works.md) · [Data model](../product/data-model.md) ·
[Evaluation protocol](../../evaluation/README.md) · [Pilot protocol](../pilot/README.md) ·
[Deployment runbook](../../deploy/README.md) · [Evidence register](../evidence/README.md)
