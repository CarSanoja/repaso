# Dev log — Plan 001: hackathon entry decision and build plan

**Date:** 2026-08-20
**Domain:** Plan

## The decision

Repaso enters the AWS **Agents for Humans Hackathon** (deadline Sep 14, 2026; Strands
Agents SDK required; Bedrock AgentCore recommended; public MIT repo; all materials in
English). Product: a reinforcement tutor for families who cannot afford one. The parent
is the only adult user; they feed the agent whatever material the school sends, and the
agent runs a daily adaptive micro-practice loop over Telegram, regulated by measured
performance, interrupting a human only for real decisions.

Two adversarial reviews preceded the GO. The first killed a materials-adaptation idea
(it matched the hackathon's own suggested example and a mature commercial niche). The
second — after a winner-forensics study of the precedent AWS AI Agent Global
Hackathon — returned GO at 70 % confidence with conditions that became the plan: hard
scope cuts, an honestly-declared simulated demo plus a small real pilot, child-safety
as a measured feature, and a web mirror so judges can test without Telegram.

## What was frozen

- Hero innovation: **Cohort Signal** — k-anonymous aggregation of struggling students
  by school-grade-section, producing a drafted teacher note the parent decides to send.
- Architecture: **13 named agents in 3 Strands graphs + a deterministic harness**.
  Agents decide *what* to practice and *when* to interrupt; auditable state machines
  own the pedagogy (SM-2 spacing, mastery EMA, escalation triggers, psychometrics).
- 100 % Amazon Bedrock for every model call; local mode runs the entire system with
  zero network using a strict playback double of the Strands model interface.
- Calendar: feature freeze Sep 3; weeks 3+ are presentation only; pilot with 5–10
  volunteer families from ~Aug 31.

## Verification

Plan approved with a test-and-benchmark plan of pre-declared gates (counts before
percentages; thresholds before results; one seed feeds the case matrix, the demo clock
and the video).
