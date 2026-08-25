# Product overview

| | |
|---|---|
| **Status** | Maintained — living document, updated with every implementation cycle |
| **Audience** | Anyone deciding whether Repaso serves their family, school, or review |
| **Last updated** | 2026-08-20 (Benchmark 001) |

Wealthy families buy reinforcement: a tutor who looks at what the child is studying,
runs a little practice every day, adapts to their level, and tells the parent when
something is genuinely wrong. Repaso is that ritual for families who cannot buy it —
an agent that lives in the family's Telegram chat, works from whatever material the
school already sends, and interrupts a human only when there is a real decision to
make.

## The parent — the only user

The account is the parent's; there is nothing for anyone else to install or learn.

1. **Feed it the chaos.** A photo of the notebook, the weekly plan PDF, even a voice
   note. Blurry photo? Repaso asks for a retake instead of guessing. Off-subject or
   too-thin material gets an honest answer, not hallucinated exercises.
2. **Set the rhythm.** Practice time, pauses, exam dates. Nine commands total;
   `/forget` erases every trace of the family after a double confirmation.
3. **Live the ritual.** Every day at the chosen hour a capsule arrives: a two-sentence
   concept reminder and three practice questions — reviews first, one new thing every
   day. Younger children practice with the parent beside them; the child never needs an
   account or the app.
4. **Decide only what is yours to decide.** When the grader is unsure about an open
   answer, the parent gets the child's exact words and two buttons. When the child has
   genuinely been struggling for days, the parent gets the evidence and three options
   with trade-offs — a guided session tonight, a drafted note for the teacher, or a
   lighter week. When the child quietly stops practicing, the parent hears about it
   that week, not at report-card time.

## The student — an experience, not an account

Short daily practice at the family's pace: immediate kind feedback, questions that
return exactly when forgetting would set in, difficulty that follows measured
performance. No login, no profile, no name — the system knows an alias and a grade,
and the strict data models physically reject anything shaped like a real identity.

## The teacher — a beneficiary, never a user

Teachers install nothing and manage nothing. When at least three families of the same
section struggle with the same competency in a week, Repaso drafts a respectful,
anonymous note — counts only, never names or aliases — and each parent decides whether
to deliver it. The classroom gets an early-warning system without a single new tool.

## The pilot operator and the judge

The operator onboards a family in ten minutes with an invite code and can watch every
number the reports publish — delivery rates, quarantine latencies, escalation counts —
from telemetry that exists from day one. Judges get a read-only web mirror with an
access code: pick a demo student, read the full transcript, drive the demo clock one
day forward through the real pipeline.

## The interruption contract

| Moment | Who is interrupted | Guarantee |
|---|---|---|
| Low-confidence open answer | Parent, one tap | The system **never guesses**; below the confidence gate no grade exists until a human decides |
| Persistent measured struggle | Parent, three options | Fires only on ≥ 8 attempts of evidence, once per cooldown; a model opinion cannot veto it — or force it |
| Quiet disengagement | Parent, weekly | Detected at the daily close, so silence itself is what triggers it |
| Section-wide struggle | Each parent of the section | k-anonymous (≥ 3 families), once per week, drafted note carries no identifiers |
| Illegible or insufficient material | Parent | A retake or an example is requested; garbage is never parsed into practice |
| Everything else | Nobody | 420 simulated student-days produced 17 interruptions — all planted, zero false |

## What Repaso refuses to do

Store a real name. Guess a grade. Message a child directly. Adapt rigor away. Publish
a family's data — the repo is open source; the data never is.
