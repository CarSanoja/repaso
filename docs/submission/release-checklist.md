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
| Offline gate | `1518 passed, 83 skipped` on the `[dev]` extra, `1642 passed, 56 skipped` with `[deploy]`; `ruff check .` clean; `check_repo_hygiene.py` clean |
| Evidence register with an explicit claim-boundaries section | [`../evidence/README.md`](../evidence/README.md) |
| Fourteen-day continuity under nine scenario gates | [`clock-14-days.json`](../evidence/clock-14-days.json); 420 sessions, 1,037 responses |
| Real Amazon Textract on a new printed Spanish page | [`live-ocr.json`](../evidence/live-ocr.json); confidence 0.9957 |
| Every configured model answers and fills its schema | [`live-conformance-2026-09-12.json`](../evidence/live-conformance-2026-09-12.json); 27 of 27 across all four model ids, and [`live-conformance-routing-2026-09-12.json`](../evidence/live-conformance-routing-2026-09-12.json); 45 of 45 on the routing that ships |
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

## Submission handoff — checked September 14, 2026

| Item | State |
| --- | --- |
| Final submitted commit and source archive SHA-256 | Record when freezing the public submission |
| Public repository, MIT license, anonymous access | `gh repo view` still reports `CarSanoja/repaso` private. MIT license exists; public source access remains pending. |
| Deployed runtime | AgentCore version 13 is deployed. Two live Telegram explanations, memory retrieval and transport links verified; see the September 14 live record. |
| Judge testing access | Loopback observer runs locally; not a public URL. A local test build and instructions exist in [`judging.md`](judging.md). Select and verify the testing path supplied in the form. |
| Public video URL, at most five minutes, English or translated | No public video URL is recorded in the submission package. The existing MP4 is a local preview; record the current working interface and publish the final video. |
| Builder ID email for submission | Owner supplies privately |
| Primary category | Good Neighbor Agents: School Community Memory. Description updated to distinguish the implemented family/observer flow from proposed school integrations. |
| Construction, provenance and individual eligibility | [`provenance.md`](provenance.md); owner verification pending |
| Three Builder Center URLs | Drafts prepared; not published |
| Availability operator through October 8 | Unassigned |
| Live evidence | Real Telegram help → retrieval → different explanation → saved memory → delivery verified twice. A scheduled practice also ran with its own correlation. Additional runs are validation options, not invented contest requirements. |
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


## Latest requirements audit

The [official rules](https://agentsforhumans.devpost.com/rules) were opened again
on September 14. The deadline is September 14 at 17:00 PDT (20:00 Caracas).
Required materials include a public code repository with MIT or Apache licensing,
README, architecture diagram, description, public YouTube/Vimeo demonstration
video of at most five minutes, and AWS Builder ID. Submission materials must be
English or accompanied by English translations. Provide working project access
or a test build with usable instructions. A live demo link is optional.

The architecture assets already exist in `docs/media/architecture.svg` and
`architecture.png`. The live record and episode runbook replace earlier statements
that nothing was deployed. Do not mark the submission complete merely because the
local frontend works: verify the public code/video links and the completed form.
No repository visibility change, publication or Devpost submission was performed
by this audit.
