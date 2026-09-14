# Agents for Humans: School Community Memory with Repaso

A child writes, “I still don't understand.” The useful next step depends on what happened before: the question, the explanation already tried, and whether the child has actually answered. That continuity is easy to lose across family messages.

The need is concrete. UNICEF's report covering 2025 estimated that 2.7 million children in Venezuela needed educational support and 1.5 million were out of school. These are national context figures, not Repaso's users or addressable market. They motivated a specific question: how can a community educator keep learning support connected between meetings? [UNICEF, end-2025 situation report, page 6](https://www.unicef.org/media/178481/file/Venezuela-Humanitarian-SitRep-No.2-(End-of-Year),-31-December-2025.pdf.pdf).

Building Repaso also led to contributions beyond this application. I submitted two upstream bug-fix pull requests to Strands Agents: [#4207](https://github.com/strands-agents/harness-sdk/pull/4207), which reads model identity through the public `Model.get_config()` interface for telemetry, and [#4208](https://github.com/strands-agents/harness-sdk/pull/4208), which aligns the declared `Model.stream()` interface with the state and trailing-block arguments the runtime supplies. Both include regression coverage. Both were open, not merged, when checked on September 14, 2026. Reliable model wrappers and traceable calls matter when an explanation must be connected to the memory and delivery it produced.

## A community problem with a practical starting point

A UNICEF account of work in Zulia in June 2020 described facilitators following up with 25 children each through visits, WhatsApp or SMS when available. That historical example informs our proposed Good Neighbor Agents use case: a community learning facilitator supporting families with foundational mathematics. It is not a partnership or a claim that this program used Repaso or Telegram. [UNICEF field account, published March 2021](https://www.unicef.org/venezuela/en/stories/education-cannot-wait-programme-doesnt-stop-during-quarantine).

The same 2025 report puts UNICEF's education response requirement at **US$23.7 million**, with a **77% funding gap**. This is a documented funding constraint for that humanitarian response, not the total economic cost of education disruption or a saving Repaso can claim. [UNICEF, Annex B, page 16](https://www.unicef.org/media/178481/file/Venezuela-Humanitarian-SitRep-No.2-(End-of-Year),-31-December-2025.pdf.pdf).

The workload has a cost even before putting a price on tutoring. As an illustrative planning calculation, 25 learners × five minutes of follow-up × five school days equals 625 minutes, or 10 hours and 25 minutes per week. The five-minute assumption is ours; this is neither measured facilitator workload nor time saved by Repaso. It identifies the work we want to reduce: reconstructing what happened before deciding how to help.

## Make a message's consequences visible

Repaso uses Telegram for supported printed fourth-grade mathematics material and short practice sessions. Strands Agents coordinates ingestion, practice planning, responses and daily review. Models run on Amazon Bedrock, and the Telegram worker invokes Amazon Bedrock AgentCore Runtime. DynamoDB retains family-scoped learning evidence, operations and delivery receipts. Application rules control evaluations, ownership and the changes made to learning state.

The new School Community Memory interface starts with a family dashboard. An adult can select a learner, topic and day; distinguish evaluated answers from requests for help; and inspect stored review dates and human decisions. Daily and cumulative views describe the evidence actually retained. A day without records stays empty. The dashboard does not invent a historical mastery curve.

Opening a topic reveals three synchronized columns: the retained conversation, the agent's observable actions and memory, and the learning evidence for that topic. Selecting a message follows its recorded links across the screen. Incoming text is a retained excerpt, not a complete Telegram export. Outgoing replies require an explicit correlation chain to delivery records. Transport acknowledgement is not a read receipt.

In our deployed Telegram demonstration, the learner asked for a different explanation of equivalent fractions. The agent retrieved the previous cake approach, used a paper-folding example, and saved that new approach. The observer connected the actual reply to its AWS memory and delivery events. Two successful requests for help left the assessed-answer count at three.

That last detail matters. Asking for help should not become an incorrect answer. And those three earlier assessments repeated the same question content: the interface exposes the repetition instead of presenting three correct responses as proof of learning improvement.

![Repaso architecture: Telegram, Strands Agents on AgentCore Runtime, durable learning memory and the read-only observer](https://raw.githubusercontent.com/CarSanoja/repaso/main/docs/media/architecture.png)

## What the demonstration establishes

The demonstrated gain is continuity that can be inspected: an earlier teaching approach is available to the next turn, the agent changes its explanation, and the adult can follow the evidence without reconstructing it from disconnected records. Replay revisits recorded turns while clearly identifying topic totals as the latest stored state.

A separate local rehearsal verifies that an adult's choice to reduce practice changes the next scheduled capsule. Its family, model responses, transport and clock are explicitly synthetic. The live Telegram interaction and this rehearsal are different kinds of evidence; neither is a family pilot or an educational impact evaluation.

The current access model is an explicit family allowlist. A complete school roster, coordinator permissions and a teacher-to-family approval workflow remain future work. Repaso requires connectivity and an adult contact. Its Good Neighbor proposal is to support the people already helping a community learn, with persistent evidence and a visible next step.

Explore the [MIT-licensed source and architecture](https://github.com/CarSanoja/repaso), follow the [local judging guide](https://github.com/CarSanoja/repaso/blob/main/docs/submission/judging.md), or inspect the [dated live demonstration evidence](https://github.com/CarSanoja/repaso/blob/main/docs/submission/memory-live-check-2026-09-14.md). The local rehearsal runs without AWS credentials or a Telegram token.

The conversation ends. The next step stays on record.
