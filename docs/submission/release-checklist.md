# Release record

Two lists. The first is finished inside the repository and can be checked by
anyone with a checkout. The second cannot be finished from a checkout at all: it
needs an account, a deployment, a person or a decision. Nothing in the second
list is ticked because a local file exists.

## Finished in the repository

| Item | Where it is, and what it printed |
| --- | --- |
| Both adult decisions run end to end and change the next session | `scripts/run_demo_scenario.py`; 24 of 24 and 23 of 23 beats as expected |
| A judge can see the product with no account and no keys | [`judging.md`](judging.md); `scripts/run_judge_demo.py` |
| Offline gate | `1287 passed, 83 skipped` on the `[dev]` extra, `1411 passed, 56 skipped` with `[deploy]`; `ruff check .` clean; `check_repo_hygiene.py` clean |
| Evidence register with an explicit claim-boundaries section | [`../evidence/README.md`](../evidence/README.md) |
| Fourteen-day continuity under nine scenario gates | [`clock-14-days.json`](../evidence/clock-14-days.json); 420 sessions, 1,037 responses |
| Real Amazon Textract on a new printed Spanish page | [`live-ocr.json`](../evidence/live-ocr.json); confidence 0.9957 |
| Every configured model answers and fills its schema | [`live-conformance-2026-09-12.json`](../evidence/live-conformance-2026-09-12.json); 27 of 27 |
| Six stacks synthesize; both ARM64 images build and serve their routes | `infra/`; [`container-smoke.json`](../evidence/container-smoke.json) |
| Deployment runbook, every command marked `[run]` or `[unverified]` | [`../../deploy/README.md`](../../deploy/README.md) |
| Independent evaluation kit, labels deliberately blank | [`../../evaluation/README.md`](../../evaluation/README.md) |
| Three-day family observation protocol, template empty | [`../pilot/README.md`](../pilot/README.md) |
| Submission copy, three article drafts, narration and captions | this directory |
| MIT license and declared dependencies | `LICENSE`, `pyproject.toml`, `requirements.lock` |

The evidence register's own base points are the September 6 implementation
commit `08826b26f8df5dbd3a125539666cbf7058f3f9cd` and evaluation commit
`42d7096fe349a741ac174f6ec5e00513ec98ae03`. Both predate the deployment and
judging work; the register says which of its rows were re-measured after them.

## Only the owner can finish these

| Item | State |
| --- | --- |
| Final submitted commit and source archive SHA-256 | Record when freezing the public submission |
| Public repository, MIT license, anonymous access | Not published |
| Deployed stacks | Not deployed. `preflight_deploy.py` reports exactly one blocker today: the account is not bootstrapped under the `repaso01` qualifier |
| Hosted judge URL and judge code | Do not exist. They fill the table at the top of [`judging.md`](judging.md) once they do |
| Public video URL, under five minutes, English captions | Not published; the local preview and script are here |
| Builder ID email for submission | Owner supplies privately |
| Primary category | Recommended: Everyday Agents |
| Construction, provenance and individual eligibility | [`provenance.md`](provenance.md); owner verification pending |
| Three Builder Center URLs | Drafts prepared; not published |
| Availability operator through October 8 | Unassigned |
| Successful real scheduled journey and ten cloud runs | Not performed. Live inference answered 930 ledgered calls on September 12; nothing is deployed |
| Family pilot and independent teacher review | Not performed; both kits prepared and empty |

Before freezing: verify the official deadline and rules, run the candidate
checks, record their outputs, open every public link in a signed-out browser and
submit. Retain the exact submitted commit, archive, captions, video and form
receipt.

Official sources: [submission requirements](https://agentsforhumans.devpost.com/),
[rules](https://agentsforhumans.devpost.com/rules),
[FAQ](https://agentsforhumans.devpost.com/details/faqs). The September 6 review
recorded September 14, 17:00 PDT / 20:00 Caracas as the deadline, and free judge
access through October 8.
