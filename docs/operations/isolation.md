# Isolation and reversal

This account already runs another system. This page states what keeps that system out
of reach of anything deployed here, what a removal takes with it, and what it leaves
standing on purpose. Read it before the first deploy.

## What is in the account today

A read-only census on September 12, 2026 found no CloudFormation stack at all, six S3
buckets in the account, and in this region nine secrets, thirteen log groups, two
Lambda functions and one DynamoDB table — every one of them named under a prefix this
project never uses. Nothing was created, changed or deleted to establish that.

Two facts follow from the first one. Everything that exists was made by another tool,
and CloudFormation removes only resources its own stacks created, so a stack of this
project cannot delete, replace or rename any of them whatever it is called. And this
project's stacks begin owning nothing, so there is no adoption, no import and no
overlap to unpick later.

## Why a deploy cannot reach any of it

Four independent things have to hold, and each is checked rather than asserted.

**Names.** Every physical name the templates set is `repaso`, `repaso-…` or
`repaso/…` — stacks, buckets, the table, secrets, queues, the bus, rules, the schedule
group, functions, log groups, the HTTP API, the runtime, the guardrail, parameters,
alarms, the dashboard, the topic and the budgets.

**Synthesis fails on anything else.** After every synth, a guard walks every resource
of every rendered template and rejects any physical name, ARN, SSM path, secret name,
log group, schedule group, cross-stack import, stack export, IAM statement resource or
principal, or resource-bearing environment variable that is not anchored in the prefix.
Intrinsics are collapsed first, so an ARN assembled by `Fn::Join` is judged as the
string it renders to. A rejected synth exits non-zero and deletes the templates it just
wrote, so a failed check cannot be deployed from a cached `cdk.out`.

**Ownership.** The stacks use their own bootstrap qualifier, `repaso01`, and its own
asset repository. They share no state with anything already deployed.

**Tags.** Every rendered resource that CloudFormation lets carry tags carries `project`,
`managed-by` and `deployment-mode`, including the ones tagged through a different
property and the helper role and function CDK creates behind an auto-emptying bucket.
The teardown reads those tags before it touches anything.

## Everything the deployed roles can address outside the prefix

This is the complete list, read out of the synthesized templates rather than from
memory. Each entry is declared by name in `infra/namespace.py` with the actions it may
carry; anything undeclared stops the build.

| What it can address | Actions | What that is |
| --- | --- | --- |
| Bedrock foundation models and inference profiles | `InvokeModel`, `InvokeModelWithResponseStream` | Model invocation. The runtime names the four model ids it uses; the Lambda grant is the whole foundation-model and inference-profile space |
| The AgentCore workload identity directory | `GetWorkloadAccessToken*` | The runtime's own identity |
| `cdk-repaso01-container-assets-*` | `ecr:BatchGetImage`, `ecr:GetDownloadUrlForLayer` | Pulling this project's own images |
| `/aws/bedrock-agentcore/runtimes/*` | create group and stream, put events, describe streams | The service-owned log namespace the runtime writes into |
| every log group in the region | `logs:DescribeLogGroups` | Lists group metadata; reads no log content |
| every schedule in the region | `scheduler:ListSchedules` | Lists schedule metadata so the runtime can find the family alarms it owns. It passes its own group name, but the action admits no resource, so the grant is region-wide. It reads no schedule target or payload and changes nothing |
| no resource | `cloudwatch:PutMetricData`, conditioned to the `repaso` metric namespace | Publishing this project's own metrics |
| no resource | `textract:DetectDocumentText` | One image per request; the action takes no resource |
| no resource | `xray:PutTraceSegments`, `PutTelemetryRecords`, sampling reads | Trace ingestion |
| no resource | `ecr:GetAuthorizationToken` | The token only; what it can pull is restricted above |
| every log group in the region | `logs:PutRetentionPolicy`, `logs:DeleteRetentionPolicy` | See below |

That last row is the only grant in the deployment that can change something outside
this project. It belongs to the helper function CDK creates to set a retention period
on the AgentCore runtime's log group, which the service creates and CloudFormation
therefore cannot own. The grant cannot read, write or delete log content; it can change
how long a group is kept, on any group in the region. CDK offers no narrower form of
it. The alternative is to drop automatic retention on that one group and set it by
hand; that is a decision, not an oversight.

## What a removal takes, by mode

The mode is fixed by the deploy that created the stacks and is read back from their
tags, never from a flag on the removal.

| | `durable` (default) | `ephemeral` |
| --- | --- | --- |
| Stacks and everything inside them with a delete policy | removed | removed |
| KMS key | retained | scheduled for deletion, seven-day pending window |
| Media bucket and every object in it | retained | emptied of every version and delete marker, then removed |
| State table and every family record | retained | removed with its contents |
| Project secrets left behind | reported, not removed | force-deleted so the names are reusable |
| Log groups that outlive their stacks | reported, not removed | removed |
| What the foundation stack's `RetainedOnDelete` output says | `kms key, media bucket, state table` | `none` |

Schedules go with the schedule group in both modes, so no delivery outlives the
deployment that created it. A durable removal keeps the records and stops the
deliveries.

## What the removal will not touch

The script discovers only names inside the prefix, so it cannot address anything else
even if asked. It then checks `project=repaso` on each candidate, and re-checks it
immediately before each target is touched. One candidate inside the prefix without the
tag, or one carrying the tag from outside the prefix, aborts the whole run with exit
code 2 and deletes nothing. Stacks that disagree about the mode abort it too.

It knows four kinds of thing: stacks, buckets, secrets and log groups. Anything else is
refused by kind. The CDK bootstrap stack and the `cdk-repaso01-*` asset repository sit
outside the prefix and are never touched; removing those is a separate, deliberate
operation.

Run against this account read-only, the planner selected nothing: prefix-bound
discovery returned zero stacks, zero buckets, zero secrets and zero log groups. Put
through the same refusal rule by hand, all thirty-one resources that exist today are
refused — twenty-eight as outside the namespace, three as kinds it cannot remove. A
production bucket that somehow carried `project=repaso` would still be refused for its
name, and a bucket named inside the prefix without the tag would abort the run.

## What none of this establishes

No stack of this project has been deployed, here or anywhere, and the bootstrap for the
`repaso01` qualifier has not been performed. The removal path — stack deletion order,
bucket emptying, secret force-delete, log group removal — is tested against fakes, not
against AWS; `--apply` has never been run. Everything above about templates is read out
of a synthesized assembly, which is a description of a deployment and not a deployment.
