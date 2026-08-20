# Infrastructure

Fully isolated from any other workload in the account: every resource is named or
prefixed `repaso`, tagged `project=repaso`, and lives in its own CloudFormation
stacks. Serverless throughout — at rest the system costs approximately nothing.

## Deploy

```bash
pip install -e ".[deploy]"
cd infra
AWS_PROFILE=quanta npx cdk deploy --all -c alert_email=<your-alerts-email>
```

The `alert_email` context enables $25 and $40 monthly budget alarms. It is passed
at deploy time and never committed.

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
