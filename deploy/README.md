# Deployment runbook

Nothing in this repository has ever been deployed. This is the ordered procedure
for the first deployment and for every one after it.

Every command below is marked. **[run]** means it was executed against the
authorized account while this runbook was written and the output shown is real.
**[unverified]** means it mutates AWS, was deliberately not executed, and its
timing is an estimate rather than a measurement. Nothing here claims a stack is
deployed; a template, an image, or a green preflight is preparation.

Use only the authorized profile and `us-east-1`. Deploy only resources prefixed
`repaso`. The account id belongs in your shell, not in this file.

## What gets created

Six stacks, deployed in this order. `cdk ls` prints it **[run]**:

```
$ cdk ls
repaso-foundation
repaso-messaging
repaso-guardrails
repaso-api
repaso-agentcore
repaso-observability
```

| Stack | What it creates | Survives teardown |
| --- | --- | --- |
| `repaso-foundation` | KMS key `alias/repaso`, media bucket (SSE-KMS, 90-day expiry), curriculum bucket, DynamoDB table `repaso` with `gsi1` and PITR, three Secrets Manager entries, two monthly budget alarms | key, media bucket, table |
| `repaso-messaging` | Event bus `repaso`, three work queues with their dead letter queues, the schedule tick dead letter queue, three routing rules, schedule group `repaso`, role `repaso-scheduler` | nothing |
| `repaso-guardrails` | Guardrail `repaso` and one published version, two SSM parameters | nothing |
| `repaso-api` | Three ARM64 container Lambdas (`repaso-webhook`, `repaso-worker`, `repaso-scheduler`), their log groups, the HTTP API and its routes, the daily-close rule | nothing |
| `repaso-agentcore` | The AgentCore runtime `repaso`, its execution role, the ARM64 runtime image, `/repaso/agentcore/runtime-arn`, seven-day log retention | nothing |
| `repaso-observability` | SNS topic `repaso-alerts`, eleven alarms, one dashboard | nothing |

A stack that imports another stack's output cannot be updated independently of
it. `repaso-agentcore` imports from all four stacks above it, so deploy and tear
down in the order `cdk ls` prints.

## What you must supply

| Input | Where it goes | Consequence if missing |
| --- | --- | --- |
| Telegram bot token | `repaso/telegram`, field `bot_token` | With the secret still holding its generated value, `_secret_field` cannot parse it as JSON and hands back the whole string, so the runtime builds a sender around a token Telegram will reject. Nothing reaches a family, and the failure appears at delivery rather than at startup. Leave the field genuinely empty and `build_channel_sender` raises instead, and every invocation answers `handler_failed`. |
| Telegram webhook secret | `repaso/telegram`, field `webhook_secret` | The webhook rejects every update with 401. |
| Judge access code | `repaso/judge`, field `code` | `/judge/login` answers 503. |
| Pilot invite codes | `repaso/pilot-invite-codes`, shape in `tools/invite_codes.py` | Enrollment closes; nobody can join. |
| Alert email | `-c alert_email=...` at deploy time | No budget alarms and no SNS subscription are created at all. |

The foundation stack creates all three secrets with a generated random string.
None of them is usable until you overwrite it, and none of them announces that
it has not been. Keep every value out of commands that land in shell history,
out of commits, out of logs and out of recordings.

## Before you deploy

Install the project and the deploy extra into the virtualenv, then run the
offline gate **[run]**:

```
pip install -c requirements.lock -e ".[dev,deploy,runtime]"
REPASO_LOCAL_MODE=true pytest -q
ruff check .
python scripts/check_repo_hygiene.py
```

Then read the account. `scripts/preflight_deploy.py` changes nothing: it
describes, gets and lists, and makes one four-token model call that `--no-inference`
skips. It exits non-zero on a blocker **[run]**:

```
$ AWS_PROFILE=quanta python scripts/preflight_deploy.py --profile quanta
repaso deploy preflight: region us-east-1, bootstrap qualifier repaso01
  ok       identity                                   arn:aws:iam::<account>:user/<caller>
  ok       region                                     us-east-1
  blocker  cdk bootstrap                              /cdk-bootstrap/repaso01/version does not exist
           -> npx aws-cdk@2 bootstrap --qualifier repaso01 --toolkit-stack-name CDKToolkit-repaso aws://<account>/us-east-1
  ok       model us.anthropic.claude-sonnet-4-6       ACTIVE
  ok       model us.anthropic.claude-haiku-4-5-20251001-v1:0 ACTIVE
  ok       model us.amazon.nova-lite-v1:0             ACTIVE
  ok       model us.amazon.nova-micro-v1:0            ACTIVE
  ok       bedrock inference                          us.amazon.nova-micro-v1:0 answered in 1/4 tokens
  ok       docker                                     linux/arm64
  ok       secret repaso/telegram                     absent, and the foundation stack creates it
  ok       secret repaso/judge                        absent, and the foundation stack creates it
  ok       secret repaso/pilot-invite-codes           absent, and the foundation stack creates it

1 blocker(s), 0 warning(s)
fix every blocker above before deploying:
  - cdk bootstrap: /cdk-bootstrap/repaso01/version does not exist
```

Build both images and start them. Both are `linux/arm64`; AgentCore accepts no
other architecture **[run]**:

```
docker build --platform linux/arm64 -f deploy/agentcore/Dockerfile -t repaso-agentcore:candidate .
docker build --platform linux/arm64 -f deploy/lambda/Dockerfile -t repaso-lambda:candidate .
```

On an Apple Silicon machine the runtime image's dependency install takes 38
seconds and its export 8, and the result is 408 MB on disk, 94 MB of compressed
layers. The Lambda image takes 37 and 10 seconds and is 963 MB on disk, 232 MB
compressed. Both emit one Docker lint
warning, `FromPlatformFlagConstDisallowed`, because the runtime Dockerfile pins
`FROM --platform=linux/arm64`; that pin is deliberate and the warning is not
actionable. `pip` also warns about running as root inside the image, which is
what a container build does.

Start the runtime image and check its two routes **[run]**:

```
$ docker run -d -p 8080:8080 -e REPASO_LOCAL_MODE=true -e REPASO_LOCAL_DATA_DIR=/tmp/repaso repaso-agentcore:candidate
$ curl -s localhost:8080/ping
{"status":"Healthy","time_of_last_update":1789189349}
$ curl -s -XPOST localhost:8080/invocations -H 'content-type: application/json' -d '{"kind":"not_a_kind"}'
{"ok": false, "kind": "not_a_kind", "error": {"code": "unknown_kind", ...}}
```

A 200 from `/ping` proves the container starts and serves. It says nothing about
whether the fleet can run: a malformed payload is rejected before any service is
constructed, so this check cannot see a missing Telegram token or an unreachable
model.

Synthesize. It needs no credentials and no Docker daemon and takes about five
seconds **[run]**:

```
$ cd infra && python app.py
```

`cdk.json` runs the app as `python3 app.py`, so the virtualenv must be first on
`PATH` when you use the CDK CLI. Without it the CLI reports a synthesis failure
that is really a missing `aws_cdk` import.

## Deploy

### 1. Bootstrap **[unverified]**

The synthesizer is pinned to qualifier `repaso01`, so the default bootstrap
stack will not satisfy it. Give the toolkit stack its own name so it cannot
collide with an existing one in the same account:

```
npx aws-cdk@2 bootstrap --profile quanta --qualifier repaso01 \
  --toolkit-stack-name CDKToolkit-repaso aws://<account>/us-east-1
```

Creates the staging bucket `cdk-repaso01-assets-<account>-us-east-1`, the ECR
repository `cdk-repaso01-container-assets-<account>-us-east-1`, and five roles:
deploy, file-publishing, image-publishing, lookup and CloudFormation execution.
Both names appear in the synthesized templates, so they are what the stacks
expect. Expect two to three minutes.

Without `--cloudformation-execution-policies` the deployment role gets
`AdministratorAccess`. This account holds unrelated infrastructure, so pass a
narrower managed policy if that matters to you; the stacks need CloudFormation,
IAM, Lambda, DynamoDB, S3, KMS, SQS, EventBridge, Scheduler, Secrets Manager,
SSM, API Gateway, CloudWatch, ECR, Budgets, SNS, Bedrock and BedrockAgentCore.

Check after: re-run the preflight. The `cdk bootstrap` line turns `ok`.

If it fails: an `AlreadyExistsException` on `CDKToolkit-repaso` means a previous
attempt left a stack in `ROLLBACK_COMPLETE` — delete that stack and run again. A
qualifier mismatch shows up later, not here, as `BootstrapVersion` resolving to
no value during the first `cdk deploy`.

### 2. Deploy every stack **[unverified]**

```
cd infra
AWS_PROFILE=quanta npx aws-cdk@2 deploy --all -c alert_email=<your address>
```

The CLI prompts before every stack that creates or widens a role — foundation,
messaging, api and agentcore. Answer each prompt, or pass
`--require-approval never` once you have read the diff.

Read the diff first; it is read-only and works without a bootstrap **[run]**:

```
$ cdk diff repaso-guardrails
Stack repaso-guardrails (aws://<account>/us-east-1)
Resources
[+] AWS::Bedrock::Guardrail Guardrail Guardrail
[+] AWS::Bedrock::GuardrailVersion PublishedVersion PublishedVersion
[+] AWS::SSM::Parameter GuardrailIdParameter GuardrailIdParameterAEAC7ABE
[+] AWS::SSM::Parameter GuardrailVersionParameter GuardrailVersionParameter8676C91B
```

Estimated durations, none of them measured:

| Stack | Estimate | Why |
| --- | --- | --- |
| `repaso-foundation` | 3-5 min | KMS key and bucket creation dominate |
| `repaso-messaging` | 2-3 min | queues and rules only |
| `repaso-guardrails` | 2-4 min | the guardrail must reach `READY` before its version publishes |
| `repaso-api` | 10-25 min | builds the Lambda image once and pushes about 232 MB to ECR, then creates three functions; the push is the variable |
| `repaso-agentcore` | 10-20 min | builds and pushes the runtime image (about 94 MB), then creates the runtime, which pulls it |
| `repaso-observability` | 2-3 min | alarms and one dashboard |

What to check after each:

- **foundation**: `aws secretsmanager list-secrets --query "SecretList[?starts_with(Name,'repaso/')].Name"` returns three names. `aws dynamodb describe-table --table-name repaso --query 'Table.TableStatus'` returns `ACTIVE`. Two budgets exist.
- **messaging**: `aws sqs list-queues --queue-name-prefix repaso` returns seven queues, four of them dead letter queues.
- **guardrails**: `aws ssm get-parameter --name /repaso/guardrail/version` returns a number, not `DRAFT`.
- **api**: the stack output `HttpApiUrl`. `curl <url>/health` must return `{"status":"ok"}`. If it returns `{"ok": true}` the application raised and the handler downgraded the failure to an acknowledgement — the route is up and the app is broken. Read the function's log group.
- **agentcore**: `aws ssm get-parameter --name /repaso/agentcore/runtime-arn`, then `aws bedrock-agentcore-control get-agent-runtime --agent-runtime-id <id> --query 'status'` must be `READY`. A `CREATE_FAILED` here is almost always the image: wrong architecture, or a container that does not answer `/ping` on 8080 within the startup window.
- **observability**: the `repaso` dashboard renders and the eleven alarms are `OK` or `INSUFFICIENT_DATA`, not `ALARM`. Open the confirmation mail SNS sends to the alert address: until it is confirmed the topic has no subscriber and every alarm fires into nothing.

If a stack fails: CloudFormation rolls it back and the ones before it stay. Fix
and re-run the same `deploy --all`; it skips what is already current. A rollback
that itself fails leaves `UPDATE_ROLLBACK_FAILED`, which needs
`continue-update-rollback` before anything else will proceed.

### 3. Fill the secrets **[unverified]**

```
aws secretsmanager put-secret-value --secret-id repaso/telegram \
  --secret-string file://<path outside the repository>
aws secretsmanager put-secret-value --secret-id repaso/judge --secret-string file://...
aws secretsmanager put-secret-value --secret-id repaso/pilot-invite-codes --secret-string file://...
```

`repaso/telegram` is JSON with `bot_token` and `webhook_secret`. `repaso/judge`
is JSON with `code`. Read the value from a file so it does not enter shell
history. Nothing caches these for long: the runtime resolves the token once per
cold start and re-reads invite codes every five minutes.

### 4. Point Telegram at the API **[unverified]**

```
curl -sS -X POST "https://api.telegram.org/bot<token>/setWebhook" \
  -d "url=<HttpApiUrl>/telegram/webhook" -d "secret_token=<webhook_secret>"
```

This changes an external integration and is the only irreversible step in the
list. Check with `getWebhookInfo`: `pending_update_count` should fall to zero and
`last_error_message` should be absent.

### 5. Accept it

1. Run the bounded live tier and keep the report. It calls real models, prices
   itself before the first call and refuses a run over its budget **[run]**:

   ```
   $ REPASO_LIVE_TESTS=1 REPASO_AWS_REGION=us-east-1 REPASO_LIVE_SAMPLES=3 pytest tests/live -s
   schema conformance at 3 samples per schema
   role       schema             calls   ok       in     out       usd
   classify   IntakeDecision         3    3     2763      60    0.0002
   generate   GeneratedBatch         3    3     4581    3531    0.0667
   generate   Snippet                3    3     2550     430    0.0141
   generate   TeacherNote            3    3     2550     445    0.0143
   judge      CriticFinding          3    3     4554     629    0.0231
   judge      OpenGrade              3    3     3447     483    0.0176
   probe      ProbeAnswer            3    3     1551      45    0.0001
   structured MappingDecision        3    3     3819     165    0.0046
   structured PolicyDecision         3    3     2682     255    0.0040
   total                            27   27    28497    6043    0.1447
   parsed 27/27, estimated spend $0.1447
   ```

   This ran on 2026-09-12 against the authorized account. All four configured
   inference profiles answered. It proves the models fill the schemas; it proves
   nothing about the deployed stacks.
2. Check `/health`, `/healthz`, `/readyz`, `/judge/`, POST `/judge/login` and a
   protected demo request on the real URL. A login is a POST; the API forwards
   every judge method.
3. Enroll a synthetic family through the actual bot. Confirm its Scheduler
   timezone and schedule, upload a printed sheet that is not in the cassette, and
   wait for one real scheduled delivery.
4. Trace one event from webhook through queue, worker, AgentCore and Telegram
   receipt. Confirm the body says `ok: true`, not merely HTTP 200.
5. Complete ten consecutive cloud journeys with real model calls: adult correct
   and incorrect review, teacher-note and reduce-load branches, pause and resume,
   a schedule change and an erase. Keep the inputs synthetic and the budget
   bounded. Never replay a real family's response as a fault test.
6. Inspect the dashboard, the four dead letter queues, pending work and the
   seven-day log retention. Stop on unexplained duplicates, unrecoverable state
   or an ownership leak.
7. Check the public demo and its links anonymously, and assign an operator and a
   budget before any family joins.

## Monthly cost at pilot scale

Rates read from the AWS Price List API for `us-east-1` on 2026-09-12. Call
volumes come from `scripts/run_demo_clock.py --days 3 --seed 20260901`, which
put thirty students through ninety student-days and made 457 model calls — 5.1
per student-day, 93 generate, 118 judge and 246 structured. Token sizes come
from the live conformance run above. Two columns: one family and thirty
families, twenty-two school days each.

| Line | Basis | 1 family | 30 families |
| --- | --- | --- | --- |
| Bedrock, Anthropic | 2.3 Sonnet 4.6 calls per student-day at $3.30/$16.50 per M tokens and 2.7 Haiku 4.5 at $1.10/$5.50 | $0.58 | $17.30 |
| Bedrock, Nova | one classify and one probe per student-day at $0.06/$0.24 and $0.035/$0.14 per M | $0.00 | $0.05 |
| CloudWatch custom metrics | $0.30 per metric-month; the simulation alone mints 41 distinct names and production paths raise it to roughly 80-150 | $24.00 | $45.00 |
| CloudWatch alarms | eleven alarms, of which three are metric-math over two metrics each, so fourteen alarm-metrics at $0.10 | $1.40 | $1.40 |
| Secrets Manager | three secrets at $0.40, plus API requests at $0.05 per 10,000 | $1.25 | $1.30 |
| KMS | one customer-managed key at $1.00, requests at $0.03 per 10,000 | $1.00 | $1.00 |
| AgentCore Runtime | one session per family per day; memory $0.00945 per GB-hour billed through the 900-second idle timeout, CPU $0.0895 per vCPU-hour billed only while processing; container measured at 59 MiB idle | $0.05 | $1.40 |
| Lambda | ARM64 at $0.0000133334 per GB-second; the worker holds 1 GB for the whole AgentCore call, which dominates | $0.01 | $0.33 |
| DynamoDB | on-demand at $0.625/M writes and $0.125/M reads, under the 25 GB free storage tier, plus PITR at $0.20 per GB-month | $0.20 | $0.25 |
| ECR | about 326 MB of compressed layers at $0.10 per GB-month, growing with every deploy | $0.03 | $0.03 |
| CloudWatch Logs | seven-day retention, about 400 bytes per trace event at $0.50 per GB ingested | $0.01 | $0.10 |
| Textract | $1.50 per 1,000 pages, one page per material upload | $0.01 | $0.18 |
| API Gateway, SQS, EventBridge, Scheduler, SNS, X-Ray, S3 | $1.00/M HTTP requests, $0.40/M queue requests, $1.00/M custom events, first 14M scheduled invocations free, first 100,000 traces free, $0.023 per GB-month | $0.02 | $0.05 |
| **Total** | | **$29** | **$69** |

Three things about that table are worth more than the total.

**CloudWatch custom metrics are the largest line, and they do not shrink with
the pilot.** `CloudWatchTelemetrySink` publishes one metric per
`{kind}.{name}.{status}` triple plus a latency metric per name plus three token
metrics, and CloudWatch charges $0.30 per distinct metric name per month whether
it receives one datapoint or a million. At one family that is most of the bill.
The same sink already writes every event as a JSON line into the runtime log
group, where the whole month costs about a penny at $0.50 per GB ingested. The
cheaper shape is to publish a small fixed set of metrics — token counts,
estimated cost, delivery outcome, decision counts — and answer everything else
with a Logs Insights query over the lines that are already there. That is a
design decision about observability, so it is named here and not made here.

**The `us.` inference profiles cost ten percent more than the `global.` ones.**
`global.anthropic.claude-sonnet-4-6` and
`global.anthropic.claude-haiku-4-5-20251001-v1:0` are both `ACTIVE` in this
account at $3.00/$15.00 and $1.00/$5.00 per million. The difference is data
residency: a geographic profile keeps inference inside the US, a global profile
routes to any commercial Region worldwide. For schoolwork belonging to children
that is a policy question, not a saving.

**The daily call budget, not the table, is what bounds the bill.**
`REPASO_GLOBAL_DAILY_LLM_BUDGET_CALLS` is 400 and `REPASO_DAILY_LLM_BUDGET_CALLS`
is 40 per family. Four hundred Sonnet calls a day at the largest measured shape
is about $139 a month. That is the ceiling the reservation enforces. The monthly
AWS budgets alert; they do not stop anything.

## Teardown

```
cd infra && AWS_PROFILE=quanta npx aws-cdk@2 destroy --all
```

**[unverified]**. It removes the stacks in reverse dependency order. It does not
remove:

- the DynamoDB table `repaso`, the media bucket and the KMS key `alias/repaso`,
  all three retained on purpose so a teardown cannot erase pilot data;
- the bootstrap stack, its staging bucket or the ECR repository — `cdk destroy`
  never touches those;
- the three secrets, which enter a recovery window rather than disappearing.

Each of those is a name a later deployment wants back. A redeploy will fail on
the table name, on the key alias, and on any secret still inside its window. The
preflight reports all three as blockers before you spend twenty minutes finding
out from CloudFormation. To actually release a name: `aws dynamodb delete-table`,
`aws kms delete-alias` (the key itself needs a scheduled deletion with a minimum
seven-day window), and `aws secretsmanager delete-secret --force-delete-without-recovery`.

To stop the service without deleting anything, `scripts/infra_toggle.py off`
disables the schedules and routing rules. Inspect what it targets before running
it; it mutates the account.

## Claim boundaries

A successful synthesis is not a deployment. A built image is not a pushed image.
A green preflight is not a successful deploy. A 200 from `/ping` is not a working
fleet. The evidence register in [docs/evidence](../docs/evidence/README.md)
records what has actually been observed; its line about live inference being
unavailable was written on 2026-09-06 and is superseded by the live conformance
run above.
