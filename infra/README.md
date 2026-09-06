# Infrastructure

Six CloudFormation stacks use the `repaso` name/tag: foundation (data, KMS, secrets and budget alerts), messaging (EventBridge, SQS and Scheduler), guardrails, API (three Lambda containers and HTTP routes), AgentCore (runtime image, IAM, SSM ARN and seven-day logs), and observability.

Both API and AgentCore deployment build Linux ARM64 images. Synthesis needs no Docker daemon or AWS credentials, but uses the local CDK cache. Install with `pip install -c requirements.lock -e ".[deploy]"`, then run `python app.py` from `infra/`. Output goes to `infra/cdk.out`; `CDK_OUTDIR` overrides it.

The [deployment guide](../deploy/README.md) is the current source for release inputs and cloud acceptance. Use only the authorized Quanta profile/account. Budget alarms notify; they do not stop all charges. Database and bucket retention means stack removal does not erase pilot data. No stack is claimed deployed from synthesis alone.
