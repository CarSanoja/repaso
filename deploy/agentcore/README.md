# AgentCore Runtime

`infra/stacks/agentcore_stack.py` reads the runtime YAML, ARM64 Dockerfile and IAM policies in this directory. `DockerImageAsset` builds the image on deployment; CloudFormation owns the runtime, execution role and SSM ARN parameter. The worker in `src/repaso/lambdas/worker.py` uses `tools/agentcore.py` to resolve `/repaso/agentcore/runtime-arn` and invoke the remote runtime.

The image serves `python -m repaso.runtime.app`. `BedrockAgentCoreApp` supplies POST `/invocations` and GET `/ping` on port 8080. All eight event kinds in `runtime.yaml` are dispatched by the same application. The runtime writes transient files only under `/tmp/repaso`, resolves the Telegram token from Secrets Manager, and uses the bundled small curriculum unless a configured Knowledge Base is explicitly selected.

The runtime role is limited to the project's data and required service calls, including primary-table scans for complete erasure, deletion of S3 object versions, Scheduler lifecycle operations, Textract, Bedrock and CloudWatch metrics. CloudFormation configures seven-day retention for `/aws/bedrock-agentcore/runtimes/<runtime-id>-DEFAULT`. Application traces and metrics are emitted explicitly; the repository does not provision AgentCore Memory or claim automatic instrumented model spans.

The app's invocation body contains an `ok` result or structured error. A valid HTTP response to an unsupported kind proves dispatch and serialization only. Cloud acceptance must also construct production services, complete a real model call and observe the family receiving the result. Follow the [deployment and acceptance guide](../README.md).

References: [AgentCore invocation contract](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-invoke-agent.html), [AgentCore observability setup](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-get-started.html).
