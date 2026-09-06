# Deployment and acceptance

The implemented cloud route uses **AgentCore Runtime** for the graphs. Three ARM64 Lambda functions handle the HTTP API, queue work and schedule ticks. Both Lambda and AgentCore images install the project and constraints from `requirements.lock`; the wheel includes judge HTML/CSS/JS, curriculum fixtures and demo cassettes.

Use only AWS profile `quanta`, authorized account `811479699647`, region `us-east-1`. Deploy only resources prefixed `repaso`. Build and synthesis are preparation; a successful template or `/ping` response does not establish usable inference.

## Prepare locally

```bash
pip install -c requirements.lock -e ".[dev,deploy,runtime]"
REPASO_LOCAL_MODE=true pytest -q
python -m build --wheel --no-isolation
python scripts/check_installed_package.py
docker build --platform linux/arm64 -f deploy/lambda/Dockerfile -t repaso-lambda:candidate .
docker build --platform linux/arm64 -f deploy/agentcore/Dockerfile -t repaso-agentcore:candidate .
cd infra
python app.py
```

Synthesis writes `infra/cdk.out`. Deployment builds/pushes both images and uses the `repaso01` bootstrap qualifier. Check the actual account with `aws sts get-caller-identity --profile quanta` before any mutation. Provide the alert email outside source control. Existing unrelated Quanta infrastructure is outside scope.

## Release inputs

The foundation stack creates Secrets Manager entries. Populate `repaso/telegram` with JSON fields `bot_token` and `webhook_secret`, `repaso/judge` with `code`, and `repaso/pilot-invite-codes` with the shape documented in `tools/invite_codes.py`. Keep values out of commands, commits, logs and video. Empty invite data closes enrollment. The runtime resolves the Telegram token from Secrets Manager. The small bundled curriculum is explicitly enabled; a Knowledge Base is optional and must be configured before selecting that source.

When the concrete candidate is approved for deployment:

```bash
cd infra
AWS_PROFILE=quanta npx cdk deploy --all -c alert_email=RELEASE_ALERT_EMAIL
```

Set the Telegram webhook to the stack's actual HTTPS URL and its matching secret using the Telegram API. This changes an external integration and belongs to the release operation. Record the actual URLs and commit in `docs/submission/release-checklist.md`; do not infer a successful URL from a template.

## Cloud acceptance gates

1. Resolve Bedrock access, then run the bounded live conformance tier in `tests/live/`. Preserve errors, model IDs, prompt versions, timestamps, reported tokens and latency.
2. Check `/health`, `/healthz`, `/readyz`, `/judge/`, POST `/judge/login` and protected demo requests on the real domain. A login is POST; API Gateway forwards all judge methods.
3. Enroll a synthetic family through the actual bot. Confirm its Scheduler timezone and alarm, upload a printed sheet outside the authored cassette, and wait for one actual scheduled delivery.
4. Trace one event from webhook through queue, worker, AgentCore and Telegram receipt. Confirm the body says `ok: true`, not merely HTTP 200.
5. Complete ten consecutive cloud journeys with real model calls. Include adult correct/incorrect review, teacher-note and reduce-load branches, pause/resume, schedule changes and erase. Keep synthetic inputs and bounded budgets. Do not replay a real family's response as a fault test.
6. Inspect the dashboard, dead-letter queues, pending work and seven-day log retention. Pause on unexplained duplicates, unrecoverable state or an ownership leak.
7. Check the public demo and links anonymously, assign an operator and budget, and keep free judge access working through October 8, 2026.

## Operational limits

The global call budget is a daily hard reservation, not a total AWS spending cap. Monthly AWS Budget alarms are alerts, not service cutoffs. Include Lambda, AgentCore, Textract, DynamoDB, S3, logs and human review in any unit-cost estimate. Soft pause tools are in `scripts/infra_toggle.py`; inspect their target resources before using them. Retained databases and buckets are not erased by stack removal.

Current verified results and unfinished external gates are in [the evidence register](../docs/evidence/README.md).
