# How it works

| | |
|---|---|
| **Status** | Maintained — living document, updated with every implementation cycle |
| **Audience** | Engineers integrating, deploying, or extending Repaso |
| **Last updated** | 2026-08-20 (Benchmark 002 — adversarial round) |
| **Related** | [Product overview](product-overview.md) · [Data model](data-model.md) · [Dev log](../devlog/README.md) · [Reports](../reports/) |

## The design stance

Agents decide **what** to practice and **when a human must be interrupted**; auditable
deterministic algorithms own every number — spacing intervals, mastery, escalation
thresholds, item statistics. The pedagogy is a state machine you can inspect, not a
model's mood. This split is what makes a system that messages families about their
children defensible.

## The fleet — 13 agents, 3 Strands graphs, 1 deterministic harness

| Graph | Agents | Deterministic spine |
|---|---|---|
| **Ingest** (S3 event) | Intake Screener (Armor, fails closed) → Material Parser → Competency Mapper → Item Generator → Item Critic → Answerability Probe | Legibility metric gates OCR; draft validation; stage claims make paid stages resumable |
| **Tutor / Response** (Scheduler / reply) | Session Planner → Capsule Composer · Grader → Adaptation Policy → Escalation Composer | SM-2 due-selection with a reserved new-item slot; confidence gate + EvidenceSpan; hard rule: triggers outrank the model on interruptions |
| **Daily close** (cron) | Goal Verifier → engagement sweep → Cohort Signal → Item Tournament | Bounded rework; weekly claims; k-anonymity floor; point-biserial retirement |

Graphs are built per job with `GraphBuilder`: deterministic nodes are `MultiAgentBase`
subclasses, conditional edges close over a typed run context, and every graph sets an
execution limit. The novel pieces: the **Answerability Probe** (a simulated student
answers the item *without* the material; success means the item measures nothing) and
the **Cohort Signal** (k-anonymous section-level aggregation producing a teacher note
whose prompt never receives an alias).

## Memory hierarchy

| Tier | Contents | Backend |
|---|---|---|
| L1 — working | Per-job run context inside a graph execution | AgentCore Runtime session state |
| L2 — semantic | Curriculum taxonomy, item-bank retrieval | Bedrock Knowledge Bases (S3 Vectors) |
| L3 — durable | Families, mastery, spacing, sessions, items, escalations, grades, claims | DynamoDB single-table (+ grade log); JSON/JSONL locally |

## Model routing — 100 % Amazon Bedrock

| Role | Model | Used by |
|---|---|---|
| generate / judge | Claude Sonnet 4.6 (env-switchable to Sonnet 5) | Item Generator, Critic, open-answer Grader, note drafting, snippets |
| structured | Claude Haiku 4.5 | Competency Mapper, Adaptation Policy |
| classify / probe | Amazon Nova Lite / Micro | Armor classification, blind probe |

Per-role fallback chains on throttle; exact ids pinned in `config/models.py`. Local
mode uses **no LLM at all**: `LocalPlaybackModel` implements the Strands model
interface and raises on any unplanned call, so the offline suite is also a cost audit.

## Speed and precision, with receipts

- **16,800 virgin-seed student-days**: struggle-interrupt **precision 0.970
  [0.947–0.983], recall 0.994 [0.980–0.998]** vs a 0.300 random baseline — reached
  through a pre-registered, out-of-sample pipeline (gates committed to git before any
  run; calibration chosen on disjoint seeds; validated on seeds no analysis touched).
  Seven of eight pre-registered gates pass; the eighth stays red on the board
  ([validation](../reports/calibration-validation-2026-08-20.md)).
- **The Armor intercepts 400/400 adversarial payloads** across 9 attack families in
  both languages, including OCR-corrupted variants, at a **0 % false-block rate** on
  200 clean worksheets ([bench](../reports/armor-bench-2026-08-20.md)); student names
  and contact data are redacted before any model call on the grading path.
- **The school calendar cannot fool it**: weekends, Carnaval and Semana Santa produce
  **zero calendar-caused false disengagement alerts per 100 student-weeks**, while
  genuine dropouts are still caught within 3 school days
  ([calendar](../reports/calendar-gaps-2026-08-20.md)).
- **675 offline tests, no credentials, no network**, green in ~5 s; the demo clock
  runs 420 student-days through the real graphs in ~14 s, byte-identical per seed.
- **Crash-resume without repaying models**; **exactly-once everywhere** (update-id
  claims, weekly signal claims, conditional writes).
- **Open findings, kept red on purpose**: 11 residual struggle FPs across 40 virgin
  seeds (G2 below its bar); outage-driven silence needs a delivery-health
  precondition; recall under a real 5-day school week is being re-audited — every
  earlier recall number assumed daily practice.

## The AWS plane

Telegram webhook → API Gateway → Lambda (FastAPI/Mangum, ACK < 200 ms, never 500s to
Telegram) → EventBridge bus → SQS(+DLQ) → worker → **AgentCore Runtime** executing the
graphs, traced in AgentCore Observability. EventBridge Scheduler holds one alarm per
family — and the agent reschedules its own alarms for exam mode. Media in KMS-encrypted
S3; secrets in Secrets Manager; DynamoDB PAY_PER_REQUEST with PITR and a RETAIN policy
on pilot data. Everything is namespaced `repaso-*`, tagged, deployed by CDK, soft
on/off by one script, and costs ≈ $0 at rest.

## Running it

```bash
pip install -e ".[dev]" && pytest                 # 675 tests, fully offline
python scripts/run_demo_clock.py --days 14        # the benchmark, ~14 s
cd infra && AWS_PROFILE=quanta npx cdk deploy --all   # the isolated cloud plane
```
