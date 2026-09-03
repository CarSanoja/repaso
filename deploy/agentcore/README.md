# AgentCore Runtime

Deployment inputs for hosting the repaso Strands graphs on Amazon Bedrock
AgentCore Runtime. Everything here is a file, and every file is read by
`infra/stacks/agentcore_stack.py` at synthesis time. Nothing in this directory
calls AWS on its own.

| File | What the stack does with it |
| --- | --- |
| `runtime.yaml` | container settings, protocol and the whole `REPASO_*` environment contract |
| `Dockerfile` | the ARM64 image, built and pushed by `cdk deploy` as a `DockerImageAsset` |
| `iam/trust-policy.json` | the principal and conditions the execution role is assumed under |
| `iam/runtime-execution-policy.json` | inline policy `repaso-agentcore-runtime` |
| `iam/repaso-data-policy.json` | inline policy `repaso-agentcore-data` |

## Design decision: CDK L1, not the starter toolkit

The rest of this project's infrastructure is CDK (`infra/`), and so is this.
The earlier decision recorded here went the other way, for a reason that no
longer holds: `CfnRuntime` was described as an escape hatch that left the whole
container path — build, repository, push, digest — outside the deploy graph,
which is the property that makes CDK worth using.

`DockerImageAsset` is that path. It stages the build context at synth, and
builds and pushes the image during `cdk deploy` into the bootstrap asset
repository, so one command still deploys the stack. `aws-cdk-lib` 2.268 ships
`CfnRuntime` and `CfnRuntimeEndpoint` as a direct mapping of
`AWS::BedrockAgentCore::Runtime`; there is no L2 construct and none is needed
for a single runtime with a container artifact.

What that buys, beyond the one command: the runtime, its execution role and the
SSM parameter carrying its ARN are all in CloudFormation, so `cdk destroy --all`
removes them, and the deployed configuration is a template in the repository
rather than a build artefact on someone's machine.

The two placeholders that are still substituted at synth rather than written
into the JSON are the account and region, and the image repository ARN — the
image lives in the CDK asset repository, so the toolkit's naming convention
would have denied the pull.

## Prerequisites

- `infra/` deployed. The runtime consumes the DynamoDB table, both buckets, the
  KMS key, both secrets, the event bus, the scheduler group and the guardrail
  created by the other five stacks.
- Bedrock model access enabled in `us-east-1` for the five models in
  `src/repaso/config/models.py`, including their fallback chains.
- Docker with `buildx`, running, for `cdk deploy`. Synthesis does not need it:
  the asset is a content hash and a staged directory until deploy time.
- Deployer IAM permissions covering ECR, CloudFormation, IAM role creation,
  `iam:PassRole` and `bedrock-agentcore:*`.

## Synthesize

```bash
pip install -e ".[deploy]"
cd infra
python app.py
```

That writes every template to `infra/cdk.out`, including
`repaso-agentcore.template.json`. `tests/infra/test_synth.py` runs exactly this
and asserts against the result.

## Deploy

```bash
cd infra
AWS_PROFILE=quanta npx cdk deploy repaso-agentcore -c alert_email=<alerts-email>
```

The image is built for `linux/arm64` from the repository root using
`deploy/agentcore/Dockerfile`, which installs the project with its `runtime`
extra and serves `python -m repaso.runtime.app`. `BedrockAgentCoreApp` provides
`/invocations` (POST) and `/ping` (GET) on `0.0.0.0:8080`, which is what
AgentCore requires.

The runtime ARN lands in SSM at `/repaso/agentcore/runtime-arn` and as the
stack output `RuntimeArnOutput`. Nothing under `src/` reads that parameter
today; it is the handoff contract for whatever invokes the runtime, and it
exists so the ARN is never stranded in a local file.

## Execution role

Assembled by the stack from `iam/`. The account id, the region, the bucket
names, the KMS key id, the image repository and the guardrail id are
substituted with live references to the other stacks, so a renamed bucket
cannot drift out of the policy. No `sed` pass, no `aws iam create-role`.

A statement whose placeholder has no value is dropped rather than deployed
pointing at nothing. That is what happens to `CurriculumKnowledgeBaseRetrieve`
today: no knowledge base exists, `tools/knowledge.py` falls back to the bundled
fixture taxonomy, and the statement would grant nothing.

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
| Secrets Manager get | pilot invite codes, and the Telegram token and judge code the API layer reads | `tools/invite_codes.py`, `lambdas/bootstrap.py` |
| `events:PutEvents` on bus `repaso` | graph fan-out | `tools/event_bus.py` |
| Scheduler create/update/delete + `iam:PassRole` | one alarm per family; `alarms.py` passes `RoleArn` in the schedule target | `tools/alarms.py` |
| `textract:DetectDocumentText` | photo OCR | `tools/ocr.py` |
| `cloudwatch:PutMetricData` in namespace `repaso` | telemetry | `core/telemetry/sink.py` |
| `bedrock:Retrieve` | curriculum knowledge base | `tools/knowledge.py` |
| `bedrock:ApplyGuardrail` | intake screening | `tools/guardrails.py` |

The AgentCore baseline restricts `PutMetricData` to the `bedrock-agentcore`
namespace, but `build_telemetry_sink` writes to a namespace called `repaso` —
hence the second, separately scoped statement.

`secretsmanager:GetSecretValue` has one reader inside this runtime:
`tools/invite_codes.py`, which resolves `repaso/pilot-invite-codes` on every
message from a chat it does not recognise. That read fails closed — an
unreadable source is an empty code set, and an empty code set answers "the
pilot is not taking new families right now" — so a missing grant would not
raise anything, it would quietly shut enrolment.

The Telegram token and the judge code are read by `lambdas/bootstrap.py`, which
runs elsewhere; `runtime/context.py` builds the Telegram sender and the media
fetcher from `REPASO_TELEGRAM_TOKEN` directly. Both statements stay because the
token is the one value the stack deliberately does not carry — see below — and
resolving it from Secrets Manager inside the runtime is the better end state.

## Environment contract

`runtime.yaml` under `environment:` is the contract, and the stack builds the
runtime's environment from it. Every variable comes from
`src/repaso/config/settings.py` (prefix `REPASO_`, `case_sensitive=False`) or
from `src/repaso/config/models.py`, which reads `REPASO_MODEL_<ROLE>` straight
off `os.environ` rather than through `Settings`.

Three rules the stack enforces rather than trusts:

- Resource names are replaced with live references — table, buckets, bus,
  scheduler group, guardrail id and guardrail version — so the file's own
  values are defaults, not the deployed truth.
- A declared value that is empty is omitted rather than written as an empty
  string. `REPASO_TELEGRAM_TOKEN` is the reason: a token in the runtime's
  environment is readable by anyone who can call `GetAgentRuntime`, and it does
  not belong in a CloudFormation template.
- Everything under `never_set` is stripped. `REPASO_LOCAL_MODE` is the
  dangerous one: `Settings.derive_local_mode` sets `local_mode = not
  bool(aws_region)`, so a runtime that derives local mode starts cleanly,
  answers `/ping`, uses no LLM at all, writes to a container-local `.local_data`
  directory and quietly produces playback output. There is no error.

`REPASO_AWS_REGION`, `AWS_REGION` and `AWS_DEFAULT_REGION` are all set from the
stack's region. The last two matter because `CloudWatchTelemetrySink` calls
`boto3.client("cloudwatch")` with no region and falls back to the ambient
environment.

`REPASO_KNOWLEDGE_BASE_ID` is empty and therefore absent, and
`tools/knowledge.py` falls back to the fixture taxonomy.

## Verify

`repaso.runtime.payload.parse_request` rejects anything without a string
`kind`, and an unknown kind returns a structured error rather than raising, so
the cheapest smoke test is a deliberately bad payload — it proves the container
is serving and the dispatcher is wired without touching Bedrock:

```python
import boto3, json, uuid

arn = boto3.client("ssm", region_name="us-east-1").get_parameter(
    Name="/repaso/agentcore/runtime-arn"
)["Parameter"]["Value"]

client = boto3.client("bedrock-agentcore", region_name="us-east-1")
response = client.invoke_agent_runtime(
    agentRuntimeArn=arn,
    runtimeSessionId=f"repaso-smoke-{uuid.uuid4().hex}",
    payload=json.dumps({"kind": "not_a_kind"}),
    qualifier="DEFAULT",
)
print(json.loads(response["response"].read()))
```

`runtimeSessionId` has a documented minimum length; a short literal is
rejected. A real invocation looks like:

```json
{
  "kind": "daily_session_due",
  "family_id": "fam-001",
  "idempotency_key": "smoke-0001",
  "payload": {"student_id": "stu-001"}
}
```

`invoke_async` catches everything and converts it to an error result, so a 200
response is not the same as a successful run — read the `kind` and error code in
the body. Container logs land in `/aws/bedrock-agentcore/runtimes/repaso-*`:

```bash
aws logs tail /aws/bedrock-agentcore/runtimes --follow --region us-east-1
```

The payload schema is owned by `repaso.runtime.payload`, not by this directory.

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
cd infra && AWS_PROFILE=quanta npx cdk destroy repaso-agentcore
```

That removes the runtime, the execution role and the SSM parameter, because all
three are in the stack. The image stays in the CDK bootstrap asset repository,
which is shared with every other asset in this account and is not this stack's
to delete.
