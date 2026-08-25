# Dev log — Implementation 002: orchestration graphs, channel, API and simulator

**Date:** 2026-08-20
**Domain:** Implementation
**Fulfills:** Plan 001 (weeks-1 wiring)
**Verification:** offline suite **390 passed**; ruff clean.

## Strands graphs

Three graphs built with `GraphBuilder`, custom deterministic nodes as `MultiAgentBase`
subclasses, conditional edges closing over a typed run context, and execution limits:

- **Ingest** — parse → screen → map → generate → validate. Terminal paths compose the
  parent-facing message (re-photo, off-subject, thin material, quarantine notice).
  Stage claims make the expensive stages resumable: a crash after generation re-runs
  the graph without repaying a single model call.
- **Tutor / Response** — plan → compose, and grade → apply → adapt → escalate. The
  escalate edge fires only on the deterministic decision; quarantine prompts carry
  one-tap approve/reject buttons.
- **Daily close** — verify → engagement sweep → cohort signal → item tournament.

## State-store extension

Split by responsibility at the 200-line boundary (protocol / local / dynamo / dynamo-io)
and extended with enrollment progress, family listing and `forget_family` — the /forget
command erases every trace of a family across all three implementations.

## Channel and API

Telegram update parser (largest photo size, PDFs, voice, button callbacks) with
exactly-once acceptance over the claim ledger; the enrollment state machine (consent
with explicit accept, alias with a real-name heuristic, grade, section, schedule
parser); nine commands including double-confirmed /forget; FastAPI surface with a
webhook that never boots open (empty secret ⇒ 503) and never returns 500 to Telegram;
judge mirror behind an access code. Bilingual message catalog with tests pinning key
and placeholder parity across ES/EN.

## Simulator core

Eight deterministic student archetypes with misconception tables seeded per
(seed, student, day, item) — same seed, byte-identical transcript — plus the
answer-bank-aware stub models that let the full pipeline run offline.

## AWS account enablement (operational)

Bedrock model agreements for Claude Sonnet 4.6 / Sonnet 5 / Haiku 4.5 accepted via
CLI (use-case form automated); the region-guard IAM policy received a surgical
carve-out for `bedrock:InvokeModel*` only, applied by the founder. Per-minute quotas
have multi-million-token defaults; the day-one token tier is the only wait.
