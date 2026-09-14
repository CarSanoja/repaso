# Repaso - School Community Memory

A community educator can support many families through messages. Keeping track
of what each learner tried, where they needed help, and what should happen next
becomes a second job. Repaso turns that follow-up into persistent, inspectable
learning memory.

Families use Telegram to submit supported printed fourth-grade mathematics
material and practise in short sessions. Repaso reviews the material, maintains
a family-owned question bank, schedules practice, evaluates answers and retains
the explanation approaches it has tried. Adults can inspect the learning evidence
and handle decisions that need human judgment.

The School Community Memory interface connects the conversation to its effects.
Its family dashboard lets an adult select a learner, a topic and a day, compare
daily activity with cumulative assessment evidence, and inspect stored review
dates and human decisions. The 14- and 30-day views use the family's timezone
and identify the current single day of real activity as a starting point.
Opening a learner's topic reveals three synchronized views: retained conversation,
the agent's recorded actions and memory, and evidence for that topic. Selecting a
message reveals its linked context retrieval, saved approach and delivery records.
Replay lets a viewer inspect earlier recorded turns while keeping current topic
totals explicitly labeled. Assessments remain visible even when their original
chat text is no longer available.

## Built with Strands, with contributions upstream

The project uses Strands graph orchestration and typed model calls in a deployed
AgentCore runtime. Work on model wrappers and replay also produced two upstream
Strands bug-fix pull requests: [model ID telemetry through the public model
configuration API](https://github.com/strands-agents/harness-sdk/pull/4207) and
[streaming contracts aligned with the runtime's arguments](https://github.com/strands-agents/harness-sdk/pull/4208).
Both include regression tests and were open, not merged, when verified on
September 14. See the [verified contribution record](upstream-contributions.md).

## What we demonstrated

In the deployed Telegram trial, a learner asked for another explanation of
fraction equivalence. Repaso retrieved the previously used cake approach, offered
a paper-folding example and saved the new approach. The observer linked the actual
reply to the memory and delivery events in AWS. Both successful help requests left
the assessed-answer count unchanged at three. Those earlier three assessments
repeated the same question content, so the interface identifies that limitation
instead of presenting the result as proven learning improvement.

A separate, explicitly labeled local rehearsal exercises the adult's decision to
reduce practice and verifies its effect on the next scheduled capsule. Its model
responses, transport and clock are controlled for demonstration. This is distinct
from the live Telegram evidence; neither is a family pilot or an educational
impact evaluation.

## How it works

![Implemented Repaso architecture](../media/architecture.svg)


Strands Agents coordinates material ingestion, practice, responses and daily
review. Model roles run on Amazon Bedrock, with the Telegram worker invoking
Amazon Bedrock AgentCore Runtime. DynamoDB stores family-scoped learning state,
recoverable operations and transport receipts. Deterministic rules update the
mastery estimate and spaced practice from evaluated answers. Input and output
filters remain active. The observer reads stored evidence; it does not manufacture
model reasoning or treat transport acknowledgements as read receipts.

## Who it is for

The proposed Good Neighbor Agents use case is a community learning facilitator
supporting families between meetings, starting with fourth-grade mathematics.
The implemented access model is an explicit family allowlist. A complete school
administration system, class roster integration and a teacher-to-family approval
workflow are outside the demonstrated scope.

Repaso's promise is continuity: the next request for help can use what happened
before, and the adult can see the evidence behind the next step. It requires
connectivity and an adult contact. No school or nonprofit partnership, measured
learning gain, or replacement for teachers is claimed.
