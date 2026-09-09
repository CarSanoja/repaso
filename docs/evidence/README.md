# Evidence register — September 6, 2026, with a September 12 addition

These artifacts record the pre-commit verification after the gap remediation. The implementation is now committed locally as `08826b26f8df5dbd3a125539666cbf7058f3f9cd`, and the evaluation kit as `42d7096fe349a741ac174f6ec5e00513ec98ae03`. The release manifest records the original candidate's exact file hashes and base commit. No cloud deployment or publication has occurred. Historical August figures are not substituted for this evidence.

One row is dated September 12: on that day Bedrock answered, and the entry it replaces said it did not. Every other row is the September 6 record and is unchanged.

| Claim | Evidence | What it does and does not establish |
| --- | --- | --- |
| Both complete family choices have a consequence | [Teacher-note run](journey-teacher-note.json), [reduced-load run](journey-reduce-load.json) | 24/24 and 23/23 assertions; seven stages; authored models, synthetic family, accelerated time, local delivery |
| Complete transport recovery is exercised | `tests/integration/test_complete_transport.py`; final [verification summary](verification-2026-09-06.json) | Ten complete runs through production adapters with Moto AWS and substituted remote AgentCore/Telegram boundaries; half inject failures; all replay webhooks and queue records |
| Fourteen-day continuity passes the scenario gates | [Clock report](clock-14-days.json) | 30 synthetic students, 420 local sessions, 1,037 responses; nine gates pass; not retention or learning measured with families |
| ARM64 containers can start and serve application routes | [HTTP smoke report](container-smoke.json) | AgentCore /ping and valid daily close; Lambda health, assets, login and a 23-check judge journey; local mode without AWS inference |
| Package includes working assets and scenario data | `scripts/check_installed_package.py`; verification summary | Wheel installed into an empty environment, run from /private/tmp; both complete journeys and HTTP/assets pass |
| A new printed Spanish page is recognized outside the cassette | [Actual OCR result](live-ocr.json), [synthetic input](printed-synthetic-page.png) | One actual Textract request; no embedded text; confidence 0.9957223510742188; not an end-to-end tutor or handwriting-quality result |
| Bedrock answered on September 12 and every configured schema parsed | [Conformance report](live-conformance-2026-09-12.json); the September 6 [access check](live-inference-access.json) it supersedes | 27 of 27 calls parsed at three samples per schema across all five roles; 28,497 input and 6,046 output tokens, $0.1444 at the rates recorded in `config/pricing.py`; p50 and p95 latency per role. Not a deployment, not a family journey, and not a model quality result |
| Independent evaluation is prepared | [Validation result](answer-evaluation-validation.json), [60-answer protocol](../../evaluation/README.md) | Cases validated, zero model predictions, zero independent reviews; quality claims are not allowed |
| The teardown planner selects nothing that exists in the account today | [Dry run](teardown-dry-run.json), [isolation and reversal](../operations/isolation.md) | One read-only run against the authorized account: discovery is bound to the `repaso` prefix at the API call, returned zero stacks, buckets, secrets and log groups, and produced an empty plan. A separate census counted the 6 buckets, 9 secrets, 13 log groups, 2 functions and 1 table the account holds; those 31 were never candidates, and the refusal tally over them was worked by hand, not printed by the planner. No removal was performed, here or anywhere |
| Family-impact evidence is prepared for collection | [Pilot kit](../pilot/README.md) | Empty observation template and aggregate analyzer; no participants or savings reported |

## Claim boundaries

The ten transport runs emulate EventBridge, SQS, DynamoDB, S3 and Scheduler. They call the real adapters and graph handlers, replace the AgentCore service boundary with a local dispatch, and mock Telegram HTTP responses. They cover publication/send failures, duplicate callbacks/events, adult decisions, schedule pause/resume and erase. They are **not ten deployed live journeys**.

Application traces distinguish simulation and live origin and report tokens only when supplied by the provider. Prices are estimates from the dated table in `config/pricing.py`, excluding infrastructure and human time. The original authored cassette's usage numbers are not billing measurements.

DynamoDB transaction tests and local WAL tests cover duplicate/conflicting learning effects. Telegram delivery remains at least once when acknowledgment is lost. Family deletion covers active records and S3 versions; retention of logs, backups and Telegram history is described in the consent.

Remaining external gates: actual cloud deployment and scheduled delivery; an observed removal, since the teardown script's stack deletion, bucket emptying and secret force-delete have only ever been planned, never executed; independent labels/calibration and probe ablation; observed families and teacher feedback; public repository, hosted demo, video, articles and submission identity/provenance. None is marked complete because a local file exists. Model access is no longer one of them, but a run of twenty-seven probe calls says nothing about sustained throughput under a pilot's load.
