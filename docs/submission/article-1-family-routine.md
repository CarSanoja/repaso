# Agents for Humans: How Repaso turns a school page into a family routine

Generating another worksheet is only one part of helping a child practice. Someone must find the material, decide what to repeat, remember tomorrow's session and recognize when a mistake deserves help. In Repaso, that person is the parent. The project asks whether an agent can complete more of that repeated work while keeping the parent in control.

The current version starts with a printed fourth-grade math page. It runs in the parent's Telegram chat, so the child needs no new account. The family chooses an alias and a practice time. Enrollment creates a timezone-aware alarm; pausing the family disables it, and changing the time updates the same schedule. The agreed routine matters as much as the generated text.

The demonstration follows a fictional family practicing equivalent fractions. A recognition question is followed by reasoning. One explanation claims that adding the same number to numerator and denominator preserves the value. The feedback gives a counterexample. Another explanation is ambiguous; the model's response is held for an adult instead of silently changing mastery.

That review needs context. The parent sees the question, the child's answer, the expected answer and a short rubric in one message. They can mark it correct, incorrect or leave it unresolved. Either final answer is retained as a human assessment. Waiting is not approval, and rejection does not disappear from the learning history.

After two labeled jumps in simulated time, repeated difficulty reaches the configured evidence threshold. The parent chooses between receiving a note for the teacher and reducing practice for seven days. The note is delivered to the parent to review and forward. In the other branch, the next session contains one exercise. This is the crucial product test: a decision must change what happens next.

The judge experience makes these stages visible without IDs or command-line work. It runs the application graphs in isolated state with authored model responses. Its dates, conversation and assertions are synthetic. A separate real Textract call recognized a new printed Spanish fractions page, but Bedrock inference remains blocked by the authorized account's quota. No live family benefit is claimed.

The next evaluation measures adult attention directly. A three-day pilot kit records preparation, accompaniment, review, corrections and operator help, with a comparable manual task. The desired result is practical—less preparation or a routine a family chooses to repeat. A small observational pilot would not establish improved learning.

Repaso belongs in Everyday Agents because the parent is the main user. Its differentiator is the work between messages: scheduling, following evidence, adjusting practice and bringing the adult a decision with context. The scope remains one child, fourth-grade math and supported printed material until broader inputs are tested.

Try the reproducible journey from the repository README. The [current evidence register](../evidence/README.md) distinguishes simulation, actual service checks and work still awaiting people or cloud access.
