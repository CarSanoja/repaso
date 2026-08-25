# Dev log — Implementation 001: foundation, tools layer and the 13-agent fleet

**Date:** 2026-08-20
**Domain:** Implementation
**Fulfills:** Plan 001 (weeks-1 foundation)
**Verification:** offline suite **337 passed** at close of this cycle; ruff clean; every
module landed with its tests in the same commit.

## Foundation

MIT skeleton, `Settings` with local-mode auto-derivation (no AWS region configured ⇒
the whole system runs offline), lazy cached boto3 factories that return `None` in local
mode, and the model-routing map (Claude for generation and judging, Nova for cheap
classification) overridable per role via `REPASO_MODEL_<ROLE>`. CI runs lint plus the
offline suite with no credentials and no network. Twenty-one strict Pydantic schema
modules; unknown fields — including any attempt to store a real student name — are
rejected at the model boundary.

## Deterministic harness

SM-2 scheduler, mastery EMA with streaks, escalation triggers with minimum-evidence and
cooldown guards, image-legibility scoring calibrated on generated photos (sharp ≈ 6465
vs radius-6 blur ≈ 150), an exactly-once claim ledger, budgets with a circuit breaker
and bounded attempts, item psychometrics (p-value, point-biserial discrimination), and
an injectable clock. No `datetime.now()`, no randomness, no LLM anywhere in this layer.

## Tools layer (the Protocol pattern)

Every external dependency sits behind a `@runtime_checkable` Protocol with a local
implementation under `local_data_dir` and a cloud implementation that acquires its
client lazily: DynamoDB single-table state store (key map in
`docs/product/data-model.md`) with conditional-write claims, S3 media, Bedrock Converse
model factory with the strict `LocalPlaybackModel` double, fail-closed Guardrails
screener with PII redaction, Telegram sender with a local outbox, EventBridge Scheduler
alarms, event publishing, Textract extraction, and a 24-competency primary-math
taxonomy for retrieval.

## The fleet

Thirteen agents in six grouped modules, each with versioned prompts: intake screener
(Armor, fails closed), material parser (legibility-gated, never spends OCR on garbage),
competency mapper (retrieval-grounded, hallucinated ids filtered), item generator
(drafts validated deterministically), adversarial item critic, blind answerability
probe (an item answerable without the material measures nothing — rejection rate is a
headline metric), session planner, capsule composer, never-guess grader (confidence
gate → parent quarantine; every grade carries an EvidenceSpan), adaptation policy with
the hard rule in code — deterministic triggers outrank the model on interruptions —,
escalation composer whose teacher-note prompt never receives the student alias, goal
verifier with bounded rework, and the item-lifecycle tournament.

## Process note

Implementation ran as three parallel agent workflows (5 + 8 + 6 workers) against
module-level specifications; every worker delivered lint-clean code with green tests
and reported upstream-contribution candidates, later curated for builder.aws.com.
