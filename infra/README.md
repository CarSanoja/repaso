# Infrastructure

Six CloudFormation stacks use the `repaso` name/tag: foundation (data, KMS, secrets, the alerts topic and tag-filtered budgets), messaging (EventBridge, SQS and Scheduler), guardrails, API (three Lambda containers and HTTP routes), AgentCore (runtime image, IAM, SSM ARN and seven-day logs), and observability.

Both API and AgentCore deployment build Linux ARM64 images. Synthesis needs no Docker daemon or AWS credentials, but uses the local CDK cache. Install with `pip install -c requirements.lock -e ".[deploy]"`, then run `python app.py` from `infra/`. Output goes to `infra/cdk.out`; `CDK_OUTDIR` overrides it.

## Deployment modes

Retention is a deploy-time choice made through CDK context, like every other setting. It defaults to `durable`, so an omitted flag can never destroy data.

| | `durable` (default) | `ephemeral` |
| --- | --- | --- |
| KMS key | retained, with the alias it answers to | scheduled for deletion on a 7-day window |
| Media bucket | retained with everything in it | every object and version deleted, then the bucket |
| State table | retained with every family record | destroyed with its contents |
| Curriculum bucket, queues, secrets, functions, runtime, guardrail, alarms | destroyed | destroyed |
| What survives `cdk destroy --all` | key, media bucket, state table | nothing |

Choose `durable` for any deployment a family reaches. A removed stack, a replaced stack or a mistake must not take a child's uploads, enrollments, answers or consent record with it; recovering them afterwards is impossible, not merely slow.

Choose `ephemeral` only while the deployment is being raised and torn down repeatedly and holds nothing anyone would miss. The consequence is exact: the media bucket loses every uploaded page, the table loses every enrollment, schedule, answer, adaptation and consent record, and the key that encrypted them is scheduled for deletion. Nothing is recoverable and nothing is orphaned.

```bash
python app.py                                                          # durable
CDK_CONTEXT_JSON='{"deployment_mode":"ephemeral"}' python app.py       # ephemeral
npx cdk synth --all -c deployment_mode=ephemeral                       # ephemeral, through the CLI
```

Every stack outputs `DeploymentMode` and the foundation stack also outputs `RetainedOnDelete`, so a deployed stack says which mode produced it and what a delete would leave standing. Every resource carries `project`, `managed-by` and `deployment-mode` tags, including the budgets and the helper role and function CDK adds behind an auto-emptying bucket. Those tags are what `scripts/teardown.py` reads before it touches anything.

## Namespace guard

Synthesis fails if any rendered resource names, imports or grants access to something outside this project. The check walks every resource of every template and inspects physical names, ARNs, SSM paths, secret names, log groups, schedule groups, cross-stack imports, stack exports, policy statements and the environment settings that carry a resource identifier.

A rejected synthesis exits non-zero and deletes the templates it had just written, so a failed check cannot be ignored and deployed from a cached `cdk.out`.

Grants that genuinely address resources this project does not create are declared one by one in `namespace.py` with the actions they may carry: foundation-model and inference-profile ARNs, the AgentCore runtime log namespace, the container asset repository of this bootstrap qualifier, and the handful of actions that admit no resource at all. Anything not declared stops the build, so widening access is a visible edit rather than a silent one. [Isolation and reversal](../docs/operations/isolation.md) lists every one of those grants as the templates actually render them, and what each can and cannot touch.

## Notes

The [deployment guide](../deploy/README.md) is the current source for release inputs, deploy and teardown commands, and cloud acceptance. Every control that bounds spend or reach, and where each one is enforced, is in [the controls page](../docs/operations/controls.md). Use only the authorized Quanta profile/account. Budgets and alarms notify; they do not stop all charges, and the budgets read zero until the project cost allocation tag is activated. In durable mode, stack removal does not erase pilot data. No stack is claimed deployed from synthesis alone.
