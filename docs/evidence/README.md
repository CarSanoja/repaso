# Evidence register — September 6, 2026

These artifacts record the pre-commit verification after the gap remediation. The implementation is now committed locally as `08826b26f8df5dbd3a125539666cbf7058f3f9cd`, and the evaluation kit as `42d7096fe349a741ac174f6ec5e00513ec98ae03`. The release manifest records the original candidate's exact file hashes and base commit. No cloud deployment or publication has occurred. Historical August figures are not substituted for this evidence.

| Claim | Evidence | What it does and does not establish |
| --- | --- | --- |
| Both complete family choices have a consequence | [Teacher-note run](journey-teacher-note.json), [reduced-load run](journey-reduce-load.json) | 24/24 and 23/23 assertions; seven stages; authored models, synthetic family, accelerated time, local delivery |
| Complete transport recovery is exercised | `tests/integration/test_complete_transport.py`; final [verification summary](verification-2026-09-06.json) | Ten complete runs through production adapters with Moto AWS and substituted remote AgentCore/Telegram boundaries; half inject failures; all replay webhooks and queue records |
| Fourteen-day continuity passes the scenario gates | [Clock report](clock-14-days.json) | 30 synthetic students, 420 local sessions, 1,037 responses; nine gates pass; not retention or learning measured with families |
| ARM64 containers can start and serve application routes | [HTTP smoke report](container-smoke.json) | AgentCore /ping and valid daily close; Lambda health, assets, login and a 23-check judge journey; local mode without AWS inference |
| Package includes working assets and scenario data | `scripts/check_installed_package.py`; verification summary | Wheel installed into an empty environment, run from /private/tmp; both complete journeys and HTTP/assets pass |
| A new printed Spanish page is recognized outside the cassette | [Actual OCR result](live-ocr.json), [synthetic input](printed-synthetic-page.png) | One actual Textract request; no embedded text; confidence 0.9957223510742188; not an end-to-end tutor or handwriting-quality result |
| Bedrock is currently unavailable in the authorized account | [Access check](live-inference-access.json) | Four short actual calls, all daily-token throttled; no successful model quality, latency or cost measurement |
| Independent evaluation is prepared | [Validation result](answer-evaluation-validation.json), [60-answer protocol](../../evaluation/README.md) | Cases validated, zero model predictions, zero independent reviews; quality claims are not allowed |
| Family-impact evidence is prepared for collection | [Pilot kit](../pilot/README.md) | Empty observation template and aggregate analyzer; no participants or savings reported |

## Claim boundaries

The ten transport runs emulate EventBridge, SQS, DynamoDB, S3 and Scheduler. They call the real adapters and graph handlers, replace the AgentCore service boundary with a local dispatch, and mock Telegram HTTP responses. They cover publication/send failures, duplicate callbacks/events, adult decisions, schedule pause/resume and erase. They are **not ten deployed live journeys**.

Application traces distinguish simulation and live origin and report tokens only when supplied by the provider. Prices are estimates from the dated table in `config/pricing.py`, excluding infrastructure and human time. The original authored cassette's usage numbers are not billing measurements.

DynamoDB transaction tests and local WAL tests cover duplicate/conflicting learning effects. Telegram delivery remains at least once when acknowledgment is lost. Family deletion covers active records and S3 versions; retention of logs, backups and Telegram history is described in the consent.

Remaining external gates: usable Bedrock quota; actual cloud deployment and scheduled delivery; independent labels/calibration and probe ablation; observed families and teacher feedback; public repository, hosted demo, video, Builder articles and submission identity/provenance. None is marked complete because a local file exists.
