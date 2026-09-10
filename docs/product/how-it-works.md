# How Repaso works

The production path is Telegram → API Gateway/webhook Lambda → EventBridge → SQS → worker Lambda → AgentCore Runtime. The worker reads the runtime ARN from SSM. The runtime loads secrets through Secrets Manager, uses DynamoDB and S3 for durable data, and sends responses through Telegram. Linux ARM64 images include dependencies and browser assets. See the [deployment guide](../../deploy/README.md).

## Four Strands graphs

| Graph | Model work | Rules and durable effects |
| --- | --- | --- |
| Ingest | Content screening, curriculum mapping, item generation, critique, options-only probe | File limits and legibility first; family-owned material; cache intermediate work; activate accepted items |
| Session | Compose a short capsule | Calendar, due review, difficulty, explanation and load adaptations; persist a plan; mark delivery after acknowledgment |
| Response | Assess an open answer, propose a policy action, draft an escalation | Validate the current question; hold uncertainty; record final assessments; atomic learning updates; persist adaptations; deliver feedback |
| Daily quality | Review item behavior and draft notices | Calendar-aware engagement checks, cohort grouping, item decisions, durable notices and recovery of pending work |

Model proposals do not independently authorize effects. Pydantic validates structure; deterministic code enforces ownership, supported choices, thresholds, budgets and retry behavior. The mastery EMA and SM-2 review schedule are heuristics, not evidence that learning has occurred.

## Recovery

Channel and family leases serialize conflicting operations. An invocation records pending work before running a handler. Durable journals retain model results, decisions and outgoing messages. A repeated event reuses that work; a daily close retries pending family operations after transient failures. EventBridge acceptance is checked before webhook receipt is recorded. The worker reports failed SQS records for retry.

Local storage uses file locks and a write-ahead transaction journal. DynamoDB uses conditional transactions for mastery, spaced review and an outcome marker. Final human assessments supersede provisional model grades, including a rejected answer; the response's original day remains available after a later human review.

The outbox acknowledges messages individually. A session becomes DELIVERED only after sending. Remote acknowledgment loss can still produce a duplicate Telegram message. Database idempotency and transport delivery have different guarantees.

## Scheduling, isolation and cost

Enrollment creates a timezone-aware family alarm. Schedule changes update it; pause disables it; erase removes it. Daily close runs at 23:50 Caracas. Student/date routing uses family local time. Cohorts use an invitation-scoped normalized section key.

Owned item selection uses strongly consistent primary reads for generated material. Deletion removes dependent records and material versions before ownership roots. Operational telemetry removes direct family/student/chat identifiers from cloud logs; it retains a hashed correlation reference. Logs have seven-day retention configured by CDK, and backups may contain historical data for up to 35 days.

Every runtime model call reserves a durable family/global daily call budget before invoking the model. Defaults are 40 calls per family and 400 globally; output is capped at 4,096 tokens and SDK retries are disabled. Application retries consume new reservations. These limits bound calls, not a guaranteed monthly bill. CloudWatch receives traces, latencies and reported token usage; estimated model cost uses a dated price table and excludes other AWS services.

## Verification boundary

Ten complete adapter simulations exercise the transport chain with emulated AWS, recorded model outputs and injected failures. Separate local state tests cover concurrent outcomes, budgets and interrupted deletion. Packaging smoke checks load installed assets and execute both judge branches. Live inference and deployed acceptance remain separate gates in the [evidence register](../evidence/README.md).
