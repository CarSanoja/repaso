# Agents for Humans: Building Strands agents whose decisions survive a retry

A tutor can produce a convincing response and still fail its family. During Repaso's review, a session was marked delivered before Telegram acknowledged it. A failed send followed by a retry found an already planned session and did no useful work. The state looked successful; the family had received nothing.

The fix was not another prompt. Repaso now records a planned session and its outgoing message before sending. A durable outbox records attempts and each acknowledgment. The session becomes delivered afterward. If a later message fails, retry resumes the unacknowledged part instead of regenerating the capsule or grading the next question accidentally.

The same principle applies to human decisions. An uncertain response has a provisional model assessment. A correct or incorrect adult decision creates a stable final assessment that supersedes it. DynamoDB commits the learning state, spaced-review state and unique outcome marker conditionally in one transaction. An interruption between operations can resume without counting the response twice. The local implementation uses a write-ahead journal and file locks for the same small-demo workflow.

Strands organizes four graphs: material ingestion, session planning, response handling and daily quality review. Models classify, generate, map, judge and probe. Application code checks ownership, allowed choices, budgets and state transitions. A model's proposed adaptation is persisted with an expiry, then consumed by the next planner. Without that final read, “reduce load” would be a label rather than a feature.

The production transport is Telegram, API Gateway, webhook Lambda, EventBridge, SQS, worker Lambda and AgentCore Runtime. The worker resolves the runtime ARN from SSM and calls the remote endpoint. Both Lambda and runtime images include their dependencies for Linux ARM64; the runtime resolves its token from Secrets Manager and keeps transient files under /tmp. Synthesis is tested separately from image startup and usable inference.

Ten complete adapter simulations now run that chain with Moto emulating AWS, authored models and substitutions at the AgentCore and Telegram network boundaries. Alternate runs inject an EventBridge publication failure and Telegram failures. Webhook events and queue deliveries are repeated. The tests include enrollment, schedule lifecycle, practice, review, both adult choices and erase. They verify behavior under those substitutions; they do not prove a successful cloud deployment.

One limitation stays explicit. Telegram sendMessage has no application idempotency key. If the remote service accepts a message and its acknowledgment is lost, a retry may duplicate it. Idempotent learning effects and exactly-once visible delivery are different properties. The repository claims the first only within its tested operation contract and describes delivery as at least once.

Real inference and deployed acceptance still need the authorized account's quota restored. The useful progress is a concrete, testable path that can recover when services fail, plus documentation that says what each result actually proves.

See the [runtime invocation contract](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-invoke-agent.html) and [implementation guide](../product/how-it-works.md).
