# Experience direction: reconstruct a learning episode

User direction, 14 September 2026: the event observer is a starting point, but
not yet a compelling product experience. Clicking an episode should transform
the screen into synchronized vertical views of Telegram, the agent's recorded
activity and memory, and learning evidence by topic and content.

## Questions the product must answer

1. What is this student working on, and where do they need help?
2. What did they ask, and what did the agent actually reply?
3. What prior context was retrieved for this turn?
4. Which explanation approach changed, and which facts support that statement?
5. What happened when the student answered: correct, incorrect, held, or unassessed?
6. How much evidence exists for this topic, across distinct questions and difficulty levels?
7. What next action was actually chosen, by whom, and did it take effect?

## Implemented experience

Entry: student and topic cards, recent episodes and evidence that needs attention.
Select an episode to open three synchronized columns:

- Conversation: reconstruction from retained messages, with source and timestamps;
  do not imply a complete Telegram archive if messages were not retained.
- Agent and memory: retrieved context, observed model/tool events, saved approach,
  assessment and delivery. Link records by correlation and record references.
  Never manufacture hidden model reasoning or infer causality from timestamps alone.
- Topic evidence: assessed attempts, distinct assessed questions, correctness,
  difficulty coverage, retained approaches, stored mastery estimate and human decisions.
  No invented trend line or difficulty progression when history is unavailable.

Selecting a chat message focuses all three views on that turn. A replay scrubber
advances through recorded events; label replay explicitly. Live mode waits for
new observed records and handles delayed logs without inventing intermediate events.

## Recording sequence

Ask for help; show prior memory. Ask for another example; highlight the prior
approach as retrieved and the new approach as saved. The assessed count stays
at its baseline. Answer; show the actual result and any persisted mastery update.
Reopen the episode; show retained evidence. An adult decision and its later effect
is a further scene only after it has its own recorded proof.

Current real baseline: 3 assessed answers, all correct, from the same repeated
question content; 2 successful explanations with different recorded approaches.
This establishes an adaptive help interaction, not measured improvement on new
questions. Use “adaptive learning loop”, not a claim that the model recursively
improves itself. Learning improvement requires further assessment evidence.

## Current implementation status

The entry is now branded **School Community Memory**, with family/student/topic
filters, interactive daily and cumulative evidence, selected-day descriptions,
stored review dates and human decisions. This extends the episode experience;
it does not introduce invented historical mastery or school-wide data. The live
family currently has one day of evidence. Episode columns and text are enlarged
vertically for easier reading.

The three-column episode experience is implemented and active in the AWS observer
at port 8767. The map opens a topic into retained conversation, linked agent
activity and memory, and topic metrics. Message and timeline selection synchronize
the panels. Replay supports scrubbing and playback; future chat turns are hidden
while topic totals remain explicitly labeled as latest stored evidence.

The agent column foregrounds the previous approach and newly saved approach.
Assessment records appear as evaluation episodes even when their original chat
text is unavailable. Metrics group by student and competency, include stored
difficulty and exact-content repetition, and exclude held or unresolved results.

AWS inspection verified six existing episodes: three assessments, one failed help
request and two successful explanations. The latest explanation reconstructs the
actual reply, one prior approach loaded, and the new paper-folding approach.
No new Telegram message or AWS state mutation was needed for this interface.

The full suite passed 2129 tests (66 skipped) before the final assessment projection
addition; after that addition, all 46 API tests passed. Chrome tested the complete
rehearsal flow, live/replay selection, persistence, access, failure recovery and
three viewport sizes (1440, 900 and 390 px) without JavaScript errors or horizontal
overflow. See [the recording runbook](episode-demo-runbook.md).
