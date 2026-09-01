# Infrastructure

Fully isolated from any other workload in the account: every resource is named or
prefixed `repaso`, tagged `project=repaso`, and lives in its own CloudFormation
stacks. Serverless throughout — at rest the system costs approximately nothing.

## Stacks

| Stack | What it owns |
| --- | --- |
| `repaso-foundation` | KMS key, media and curriculum buckets, the DynamoDB table and its `gsi1`, both secrets, the budget alarms |
| `repaso-messaging` | event bus, the three work queues with their dead letter queues, the routing rules, the scheduler group and role |
| `repaso-guardrails` | the Bedrock guardrail, its published version, and both handles in SSM |
| `repaso-api` | the three Lambda functions, their log groups and event sources, the HTTP API |
| `repaso-agentcore` | the ARM64 runtime image, its execution role, the AgentCore runtime and its ARN in SSM |
| `repaso-observability` | the alert topic, the alarms on queues, functions and the API, the dashboard |

`repaso-agentcore` is documented in detail in `deploy/agentcore/README.md`,
whose files it reads at synthesis time.

## Synthesize

```bash
pip install -e ".[deploy]"
cd infra
python app.py
```

Every template lands in `infra/cdk.out`, which is ignored. `CDK_OUTDIR`
overrides that, which is how the CDK CLI and `tests/infra/test_synth.py` both
drive it. Synthesis needs no AWS credentials and no Docker daemon.

## Deploy

```bash
cd infra
AWS_PROFILE=quanta npx cdk deploy --all -c alert_email=<your-alerts-email>
```

The `alert_email` context enables $25 and $40 monthly budget alarms and
subscribes the address to the alert topic. It is passed at deploy time and never
committed. Deploying `repaso-agentcore` builds an ARM64 image and needs Docker
running; the other five stacks do not.

## Turn off / on

Soft toggle — stops all scheduled activity and event routing, keeps all data:

```bash
AWS_PROFILE=quanta python scripts/infra_toggle.py off
AWS_PROFILE=quanta python scripts/infra_toggle.py on
```

Hard teardown:

```bash
cd infra && AWS_PROFILE=quanta npx cdk destroy --all
```

The DynamoDB table and the media bucket use a RETAIN policy so pilot data
survives a destroy; delete them manually only when the data is no longer needed.
