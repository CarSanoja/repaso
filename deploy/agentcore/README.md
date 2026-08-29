# AgentCore Runtime

Deployment configuration and runbook for hosting the repaso Strands graphs on
Amazon Bedrock AgentCore Runtime.

`runtime.yaml` is the hand-maintained source of truth: entrypoint, container
settings, the `REPASO_*` environment contract, and the IAM policies the
execution role needs. The starter toolkit generates its own
`.bedrock_agentcore.yaml` when you run `agentcore configure` — that file is a
build artefact, not the specification. When the two disagree, `runtime.yaml`
wins and the toolkit invocation is corrected.

Everything here is a file. Nothing in this directory calls AWS on its own.

## Design decision: starter toolkit, not CDK

The rest of this project's infrastructure is CDK (`infra/`). AgentCore is
deliberately not. This is a recorded decision, not an oversight.

`aws-cdk-lib` ships only the L1 `aws_bedrockagentcore.CfnRuntime` escape hatch —
a direct CloudFormation mapping with no L2 construct. Using it means owning the
whole container path by hand: build an ARM64 image, create the ECR repository,
push, resolve the digest, and feed the URI into `CfnRuntime`, all outside the
CDK deploy graph. The build step cannot participate in `cdk deploy`, so the
"one command deploys the stack" property that makes CDK worth using in the first
place does not hold here.

The starter toolkit does that build-and-push path in one command. The cost of
the decision is that the AgentCore runtime is not described in
CloudFormation and is not torn down by `cdk destroy --all`; teardown is a
separate step, documented below.

Revisit this when an L2 construct for AgentCore Runtime lands in `aws-cdk-lib`.
The newer Node CLI (`npm install -g @aws/agentcore`) already wraps CDK
constructs from `@aws/agentcore-cdk` internally, which is the likely path for
that to happen.

## Prerequisites

- An AWS account with `infra/` already deployed. The runtime consumes the
  DynamoDB table, both buckets, the KMS key, both secrets, the event bus and the
  scheduler group created by `repaso-foundation` and `repaso-messaging`.
- Bedrock model access enabled in `us-east-1` for the five models in
  `src/repaso/config/models.py`, including their fallback chains.
- Python 3.12+ and the toolkit:

```bash
pip install bedrock-agentcore bedrock-agentcore-starter-toolkit
```

- Deployer IAM permissions. Start from `BedrockAgentCoreFullAccess` plus the
  policy in the *Use the AgentCore CLI* section of
  [IAM Permissions for AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html)
  — CodeBuild, ECR, S3, CloudWatch Logs, role management and `iam:PassRole`.
  That section is written for the Node CLI; it is the closest published
  equivalent for the starter toolkit, which drives the same build path.
- The runtime package under `src/repaso/runtime/`. `entrypoint.invoke(payload)`
  and `entrypoint.invoke_async(payload)` are the dispatch surface;
  `app.build_runtime_app()` wraps `invoke_async` in `BedrockAgentCoreApp` and
  `app.main()` serves it. AgentCore requires an ARM64 container serving
  `/invocations` (POST) and `/ping` (GET) on `0.0.0.0:8080`;
  `BedrockAgentCoreApp` provides both endpoints. `app.py` is the file you point
  `--entrypoint` at — see item 4 under *Needs verification*.

## Execution role

Create the role once, before `agentcore configure`. The agent name is baked
into the log-group and workload-identity ARN patterns in the policies, so
`repaso` has to be settled before the role exists.

Substitute your account id, bucket names, KMS key id, knowledge base id and
guardrail id. This uses BSD `sed`; on GNU `sed` drop the `''`:

```bash
cd deploy/agentcore
export ACCOUNT_ID=<your-account-id>
for f in iam/*.json; do
  sed -i '' \
    -e "s/123456789012/$ACCOUNT_ID/g" \
    -e "s/REPASO_MEDIA_BUCKET/<media-bucket-name>/g" \
    -e "s/REPASO_CURRICULUM_BUCKET/<curriculum-bucket-name>/g" \
    -e "s/REPASO_KEY_ID/<kms-key-id>/g" \
    -e "s/REPASO_KNOWLEDGE_BASE_ID/<knowledge-base-id>/g" \
    -e "s/REPASO_GUARDRAIL_ID/<guardrail-id>/g" \
    "$f"
done
```

```bash
aws iam create-role \
  --role-name repaso-agentcore-runtime \
  --assume-role-policy-document file://iam/trust-policy.json

aws iam put-role-policy \
  --role-name repaso-agentcore-runtime \
  --policy-name repaso-agentcore-runtime \
  --policy-document file://iam/runtime-execution-policy.json

aws iam put-role-policy \
  --role-name repaso-agentcore-runtime \
  --policy-name repaso-agentcore-data \
  --policy-document file://iam/repaso-data-policy.json
```

`iam/runtime-execution-policy.json` is the AgentCore baseline — ECR pull, the
`/aws/bedrock-agentcore/runtimes/*` log groups, X-Ray, the `bedrock-agentcore`
metric namespace, workload identity, and Bedrock model invocation scoped to the
five models this project uses plus their fallbacks.

`iam/repaso-data-policy.json` is the project data plane, derived from the boto3
clients in `src/repaso/config/clients.py` and their call sites:

| Statement | Why | Call site |
| --- | --- | --- |
| DynamoDB on `repaso` and `gsi1` | state store | `tools/state_dynamo.py` |
| S3 read/write on the media bucket | material uploads | `tools/media_store.py` |
| S3 read on the curriculum bucket | taxonomy | `tools/knowledge.py` |
| KMS decrypt/generate | the media bucket is KMS-encrypted in `FoundationStack` | — |
| Secrets Manager get | Telegram token, judge code | `lambdas/bootstrap.py` |
| `events:PutEvents` on bus `repaso` | graph fan-out | `tools/event_bus.py` |
| Scheduler create/update/delete + `iam:PassRole` | one alarm per family; `alarms.py` passes `RoleArn` in the schedule target | `tools/alarms.py` |
| `textract:DetectDocumentText` | photo OCR | `tools/ocr.py` |
| `cloudwatch:PutMetricData` in namespace `repaso` | telemetry | `core/telemetry/sink.py` |
| `bedrock:Retrieve` | curriculum knowledge base | `tools/knowledge.py` |
| `bedrock:ApplyGuardrail` | intake screening | `tools/guardrails.py` |

Three notes on that policy.

The AgentCore baseline restricts `PutMetricData` to the `bedrock-agentcore`
namespace, but `build_telemetry_sink` writes to a namespace called `repaso` —
hence the second, separately scoped statement.

`bedrock:Retrieve` and `bedrock:ApplyGuardrail` are conditional.
`runtime/context.py` passes `REPASO_KNOWLEDGE_BASE_ID` and `REPASO_GUARDRAIL_ID`
through to the retriever and the screener; when either is absent the code falls
back to the local fixture retriever or the heuristic screener and the
corresponding statement is dead. Drop the statement rather than leave a
placeholder resource in the policy.

`secretsmanager:GetSecretValue` is, as the code stands, **not** used by this
runtime. `runtime/context.py` builds the Telegram sender from
`REPASO_TELEGRAM_TOKEN` directly; the only reader of
`REPASO_TELEGRAM_SECRET_NAME` and `REPASO_JUDGE_CODE_SECRET_NAME` is
`lambdas/bootstrap.py`, which runs elsewhere. The statement is kept because
passing a bot token as a runtime environment variable puts it in the runtime's
stored configuration, readable by anyone who can call `GetAgentRuntime`; moving
the runtime to resolve its own secret is the better end state. If you are not
going to do that, remove the statement.

## Environment contract

Every variable in `runtime.yaml` under `environment:` comes from
`src/repaso/config/settings.py` (prefix `REPASO_`, `case_sensitive=False`) or
from `src/repaso/config/models.py`, which reads `REPASO_MODEL_<ROLE>` straight
off `os.environ` rather than through `Settings`.

The one that will bite you: **`REPASO_AWS_REGION` must be set**.
`Settings.derive_local_mode` sets `local_mode = not bool(aws_region)`, so a
runtime deployed without it starts cleanly, answers `/ping`, uses no LLM at all,
writes to a container-local `.local_data` directory and quietly produces
playback output. There is no error. Never set `REPASO_LOCAL_MODE` explicitly —
let it derive.

`AWS_REGION` and `AWS_DEFAULT_REGION` are also required. Most boto3 clients are
built with an explicit `region_name` from settings, but
`CloudWatchTelemetrySink` calls `boto3.client("cloudwatch")` with no region and
falls back to the ambient environment.

Three variables are read straight from `os.environ` by
`src/repaso/runtime/context.py` and have no `Settings` field, so they will not
appear in `.env.example`:

| Variable | Effect when unset |
| --- | --- |
| `REPASO_TELEGRAM_TOKEN` | `build_channel_sender` raises `ValueError` outside local mode. Required. |
| `REPASO_KNOWLEDGE_BASE_ID` | falls back to the bundled fixture taxonomy in `tools/knowledge.py` |
| `REPASO_GUARDRAIL_ID` | falls back to the heuristic screener; no Bedrock Guardrail is applied |

`REPASO_LIVE_TESTS` stays unset in the runtime.

## Configure

From the repository root:

```bash
agentcore configure \
  --entrypoint src/repaso/runtime/app.py \
  --name repaso \
  --region us-east-1 \
  --execution-role arn:aws:iam::$ACCOUNT_ID:role/repaso-agentcore-runtime \
  --requirements-file deploy/agentcore/requirements.txt \
  --protocol HTTP
```

This writes `.bedrock_agentcore.yaml` in the repository root and generates a
Dockerfile from the project. Observability is enabled by default; do not pass
`--disable-otel`.

`.bedrock_agentcore.yaml` records your account id and ECR URIs and is **not**
covered by the repository `.gitignore`. Add it before the first configure, or
keep it out of commits by hand. This repository ships publicly.

## Launch

```bash
agentcore launch \
  --env REPASO_AWS_REGION=us-east-1 \
  --env AWS_REGION=us-east-1 \
  --env AWS_DEFAULT_REGION=us-east-1 \
  --env REPASO_DDB_TABLE=repaso \
  --env REPASO_MEDIA_BUCKET=<media-bucket-name> \
  --env REPASO_CURRICULUM_BUCKET=<curriculum-bucket-name> \
  --env REPASO_EVENT_BUS=repaso \
  --env REPASO_SCHEDULER_GROUP=repaso \
  --env REPASO_TELEGRAM_SECRET_NAME=repaso/telegram \
  --env REPASO_JUDGE_CODE_SECRET_NAME=repaso/judge \
  --env REPASO_TELEGRAM_TOKEN=<telegram-bot-token>
```

Add `--env REPASO_KNOWLEDGE_BASE_ID=<id>` and `--env REPASO_GUARDRAIL_ID=<id>`
once those resources exist; without them the runtime silently uses the fixture
taxonomy and the heuristic screener.

Model ids and tuning values are left at their code defaults; override them with
further `--env` pairs only when they need to differ from
`src/repaso/config/models.py` and `settings.py`.

The toolkit builds the ARM64 image, creates the ECR repository, pushes, and
creates the runtime. Expect a few minutes.

## Capture the runtime ARN into SSM

The runtime ARN is the only handle the rest of the system has on the deployment,
and the toolkit leaves it in a local file. Publish it:

```bash
RUNTIME_ARN=$(agentcore status --agent repaso --verbose | python3 -c 'import json,sys; print(json.load(sys.stdin)["agent_arn"])')

aws ssm put-parameter \
  --name /repaso/agentcore/runtime-arn \
  --type String \
  --value "$RUNTIME_ARN" \
  --overwrite \
  --region us-east-1
```

Nothing under `src/` reads this parameter today — there is no SSM client in
`config/clients.py`. It is the handoff contract for the SQS worker that will
invoke the runtime, and it exists so that the ARN is not stranded in a local
build artefact. Whatever consumes it will need `ssm:GetParameter` on
`arn:aws:ssm:us-east-1:<account>:parameter/repaso/agentcore/runtime-arn`.

## Verify

`repaso.runtime.payload.parse_request` rejects anything without a string
`kind`, and `HANDLERS` covers four of the seven `EventKind` members:
`material_uploaded`, `daily_session_due`, `response_received`, `daily_close`.
An unknown kind returns a structured error rather than raising, so the cheapest
smoke test is a deliberately bad payload — it proves the container is serving
and the dispatcher is wired without touching Bedrock:

```bash
agentcore status --agent repaso
agentcore invoke --agent repaso '{"kind": "exam_announced"}'
```

That should come back as an `UNSUPPORTED_KIND` error result. A real invocation
looks like:

```json
{
  "kind": "daily_session_due",
  "family_id": "fam-001",
  "idempotency_key": "smoke-0001",
  "payload": {"student_id": "stu-001"}
}
```

Or through boto3:

```python
import boto3, json, uuid

client = boto3.client("bedrock-agentcore", region_name="us-east-1")
response = client.invoke_agent_runtime(
    agentRuntimeArn=RUNTIME_ARN,
    runtimeSessionId=f"repaso-smoke-{uuid.uuid4().hex}",
    payload=json.dumps({"kind": "exam_announced"}),
    qualifier="DEFAULT",
)
print(json.loads(response["response"].read()))
```

`runtimeSessionId` has a documented minimum length; a short literal is rejected.
The generated id above is comfortably past it.

A healthy deployment returns a JSON body from `/invocations`. `invoke_async`
catches everything and converts it to an error result, so a 200 response is not
the same as a successful run — read the `kind` and error code in the body.
Container logs land in `/aws/bedrock-agentcore/runtimes/repaso-*`:

```bash
aws logs tail /aws/bedrock-agentcore/runtimes --follow --region us-east-1
```

The payload schema is owned by `repaso.runtime.payload`, not by this directory.
Ignore the `{"prompt": ...}` shape in the toolkit's own documentation; this
runtime dispatches on `kind`.

### Bedrock throughput

This account currently has Bedrock on-demand throughput at zero, pending an AWS
support case. Deployment, `agentcore status` and `/ping` all work. Live
invocation will fail with `ThrottlingException` as soon as a graph reaches a
model call, and the fallback chains in `models.py` will not save it — every
fallback is also Bedrock. 100% of model calls in this project go through
Amazon Bedrock; there is no second provider anywhere and adding one is out of
scope.

Until the case clears, verify with local mode instead, which uses no LLM at all:
unset `REPASO_AWS_REGION` and run the graphs against `LocalPlaybackModel`. That
exercises orchestration, not inference.

## Observability

AgentCore Runtime instruments the container with OpenTelemetry automatically.
Nothing needs to be added to the image, and no OTEL environment variables are
set here — those are only for agents hosted outside AgentCore.

CloudWatch Transaction Search is a one-time, per-account setup, without which
spans never appear:

```bash
aws logs put-resource-policy \
  --policy-name TransactionSearchAccess \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Sid":"TransactionSearchXRayAccess","Effect":"Allow","Principal":{"Service":"xray.amazonaws.com"},"Action":"logs:PutLogEvents","Resource":["arn:aws:logs:us-east-1:'"$ACCOUNT_ID"':log-group:aws/spans:*","arn:aws:logs:us-east-1:'"$ACCOUNT_ID"':log-group:/aws/application-signals/data:*"],"Condition":{"ArnLike":{"aws:SourceArn":"arn:aws:xray:us-east-1:'"$ACCOUNT_ID"':*"},"StringEquals":{"aws:SourceAccount":"'"$ACCOUNT_ID"'"}}}]}'

aws xray update-trace-segment-destination --destination CloudWatchLogs
```

Spans take up to ten minutes to become searchable after enabling. Indexing 1% of
traces is free; raise it with `aws xray update-indexing-rule` if the sample is
too thin to debug with.

Read traces in the CloudWatch console under **GenAI Observability**. Each
invocation is one trace; the graph nodes appear as child spans, so a
`build_ingest_graph` run shows `parse → screen → map → generate → validate` with
per-node timing and the model call inside each. That is the fastest way to see
which node a `terminal` short-circuit fired on.

Two metric namespaces are in play and they are not the same thing:
`bedrock-agentcore` is what the runtime emits, `repaso` is what
`CloudWatchTelemetrySink` emits from inside the graphs. Project-level counters
live in the second one.

## Teardown

```bash
agentcore destroy --agent repaso --delete-ecr-repo
```

Then remove what the toolkit did not create:

```bash
aws ssm delete-parameter --name /repaso/agentcore/runtime-arn --region us-east-1
aws iam delete-role-policy --role-name repaso-agentcore-runtime --policy-name repaso-agentcore-data
aws iam delete-role-policy --role-name repaso-agentcore-runtime --policy-name repaso-agentcore-runtime
aws iam delete-role --role-name repaso-agentcore-runtime
```

`cdk destroy --all` does not touch any of this. The AgentCore runtime, its ECR
repository, its CodeBuild project and this execution role are outside
CloudFormation by the design decision recorded above — that is the price of not
using CDK here, and it has to be paid by hand at teardown time.

## Needs verification against the installed toolkit

The starter toolkit's CLI surface has moved between releases and this runbook
was written without the toolkit installed in `.venv`. Run `agentcore --help` and
`agentcore <command> --help` against the version you actually install and
correct this file before trusting it. The following are known-uncertain:

1. **`agentcore launch` vs `agentcore deploy`.** AWS blog posts and the
   CloudWatch observability guide use `agentcore launch`. The toolkit's current
   `documentation/docs/api-reference/cli.md` on `main` documents `agentcore
   deploy` and no `launch`. One is a rename. Confirm which your version has;
   the `--env`, `--local`, `--image-tag` and `--auto-update-on-conflict` flags
   belong to whichever it is, not to `configure`.

2. **`--env` repetition.** Documented as `--env` / `-env` taking `KEY=VALUE`.
   Whether it may be repeated (as written above) or expects a single
   comma-separated string is unconfirmed.

3. **`--deployment-type` and `--runtime`.** Current `main` documents a
   `direct_code_deploy` default with a `--runtime PYTHON_3_1x` selector;
   older versions built a container by default. `runtime.yaml` declares
   `PYTHON_3_13`. If your version defaults to `container`, `--runtime` may be
   ignored and the generated Dockerfile's base image decides the Python version
   instead.

4. **What `--entrypoint` should point at.** `src/repaso/runtime/app.py` builds
   the server inside `build_runtime_app()` and serves it from `main()`. There is
   no module-level `app` object and no `if __name__ == "__main__"` guard, so
   importing or executing that file does not start a server. The toolkit
   examples all use a module-level `app = BedrockAgentCoreApp()` with
   `app.run()` under a `__main__` guard. Either the toolkit discovers the
   factory, or `app.py` needs the guard added. Determine which before the first
   launch; this is the most likely cause of a container that builds and then
   fails its health check.

5. **How `repaso` reaches the container.** `requirements.txt` here lists third
   party dependencies only. The project uses a `src/` layout with
   `package-dir = {"" = "src"}`, so an unmodified `PYTHONPATH` will not import
   `repaso` even with the source copied in. Confirm whether the generated
   Dockerfile installs the project, and if not, add `.` to
   `deploy/agentcore/requirements.txt` or set `PYTHONPATH=/app/src`.

6. **The runtime ARN's key.** The `agentcore status --verbose` JSON path used
   above assumes `agent_arn`, which is the key the toolkit's `launch()` returns
   in the Python API. The CLI's `status` output may nest it differently; the
   same value is in the `bedrock_agentcore:` section of
   `.bedrock_agentcore.yaml`, which is the more stable read.

7. **`invoke_agent_runtime` parameter shape.** The AgentCore observability guide
   passes `payload=json.dumps(...)`. The AWS SDK for PHP reference for the same
   operation shows a structured `body` parameter instead. These are different
   API versions. Check `client.meta.service_model.operation_model("InvokeAgentRuntime").input_shape.members`
   in your installed boto3 before writing a caller.

8. **`aws-opentelemetry-distro`.** Runtime-hosted agents are auto-instrumented
   and the toolkit adds OTEL to the generated Dockerfile, so it is deliberately
   absent from `requirements.txt`. Confirm against the generated Dockerfile; if
   your version does not add it, pin it there.

9. **Upstream status.** The toolkit's own README carries a deprecation notice:
   "The Starter Toolkit CLI is no longer supported", pointing at
   `npm install -g @aws/agentcore`. That CLI is Node-based and wraps
   `@aws/agentcore-cdk`. The decision recorded above stands for now, but this is
   the tripwire that should force a revisit — not a stale-dependency warning.
