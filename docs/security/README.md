# Security posture — September 12, 2026

This is a review of the code and the synthesized infrastructure as they stand on the branch
being published. It was written against the security work alone and re-measured after that work
was merged with the deployment, judging, isolation, measurement and language work, so the counts
and the
IAM reading below describe this tree and not the one they were first taken from. It records
what was tested and how, what changed as a result, what risk remains, and which assurances
cannot exist until the system is deployed.

The same claim discipline as [the evidence register](../evidence/README.md) applies here. A
synthesized template is not a deployed stack. A local test is not a production observation. A
threat that was reasoned about but not exercised is written that way, and says so in the
"how it was checked" column.

Nothing was deployed, created, modified or deleted in any cloud account during this review. The
only cloud calls made were reads of account state and a small number of model invocations,
described under **The model boundary** below.

## What the system has to protect

Repaso ingests photographs of schoolwork, stores a record about a child, talks to a parent over
Telegram, and sends material a stranger could have influenced to a foundation model. The record
is deliberately thin — the child has no account, no login and no name in the system — but it is
still a record about a minor: an alias, a school grade, a school and section, a practice time,
uploaded pages, and every answer the child has given.

## Method

| Area | How it was checked |
| --- | --- |
| Secrets and identifiers | Every blob reachable from this branch read and pattern-matched — 1241 blobs over 266 commits — not only the working tree, and a wider sweep over every ref in the clone |
| Data protection | Schemas and storage adapters read; erasure exercised against DynamoDB and S3 with Moto, including object versions |
| IAM | CloudFormation synthesized and the rendered policy statements parsed; every inline statement of every role enumerated |
| Encryption | Read from the synthesized templates, not from intent in the source |
| Prompt injection | 24 crafted attempts against the deterministic screener; 9 against the full two-stage screener with a live model |
| Model output | Strands' Bedrock defaults read from the installed library; agent fallback paths traced by hand |
| Channel | Webhook authentication, admission and replay read and exercised through the API |
| Dependencies | `pip-audit` against the pinned lock; the project reinstalled under the edited lock and the suite re-run |

Every fix below is a separate commit carrying its own test. Where a test asserts a security
property, it was run against the code as it was before the fix to confirm it fails there — a
test that passes both ways proves nothing.

## Secrets and identifiers

**The hygiene gate could not see history.** It read `git ls-files`, so it inspected only the
files that survived to the working tree. A credential committed and later deleted stays in every
clone and the gate called the repository clean. It now reads every blob reachable from the branch
being published, and `--all` sweeps every ref for the check worth running once before a
repository is made public.

**Its pattern set was thin.** It knew six shapes. It now also knows Anthropic and Google keys,
bearer tokens, a secret access key beside its variable name, international phone numbers, and a
real account id where the IAM templates carry a placeholder — the shape a careless edit to
`deploy/agentcore/iam` would take. Each rule reports up to three hits per file instead of one, so
one fix cannot hide the next.

**Result: the history is clean.** All 1241 blobs reachable from this branch match no rule, and so
does every blob in the wider sweep over every ref, including branches not yet merged. The only
hits the strengthened gate produced anywhere were the gate's own
test fixtures, which carry synthetic secret shapes on purpose — among them AWS's published
example access key — and a fixture ARN built on a documented placeholder account id. Both are
exempted by name, not by weakening the rule.

No value matching any of these shapes — an access key, a bot or bearer token, a private key block,
an international phone number, or an account id that is not a documented placeholder — appears in
any version of any tracked file.

Two limits on that statement. A Telegram chat id is a bare integer with no distinguishing shape,
so no pattern can find one; the chat refs in the tracked fixtures were read by hand and are
synthetic (`100`, `200`, `12345`). And a rule only finds what it describes: this is evidence that
the known shapes are absent, not proof that the history holds no secret of a shape nobody thought
to write down.

## Data protection for minors

**What is stored and where.** The family record, the student record, uploaded material, practice
sessions, answers, grades, mastery estimates, exam dates, escalations and quarantined quotes all
live in one DynamoDB table. Uploaded photographs and PDFs live in one S3 bucket under
`media/<family-id>/`. Nothing else holds family data.

**Encryption at rest, corrected.** The material bucket was already encrypted with the project's
customer-managed key. The table — which holds the alias, the grade, the school and section and
every answer — carried no `SSESpecification` at all, so it fell back to the DynamoDB default: an
AWS-owned key that the account cannot inspect, audit, rotate on its own schedule or disable to
revoke access. The table now uses the same key as the bucket.

**Encryption in transit, corrected.** Neither bucket had a policy, and S3 accepts plain HTTP
unless a policy refuses it. Both buckets now deny every request arriving without TLS and every
request below TLS 1.2.

**Retention.** Material expires after 90 days by lifecycle rule. The text a child writes in an
answer expires after seven days, on a row of its own, and the attempt it belonged to stays:
that there was one, whether it was right, and when. Operational logs are retained
seven days, which is what the log groups are configured for. Backups are the 35-day
point-in-time-recovery window. The consent states the seven and the thirty-five, and both are
accurate.

**Erasure.** `/forget` pauses the family, removes the schedule, erases the grade log, deletes the
material prefix including every object version and delete marker, then scans the whole table and
deletes every row owned by the family. The scan is deliberate: a GSI or an ownership mirror alone
cannot prove erasure when a dual write was interrupted.

One gap was found and fixed. Rows under `CLAIM#` were deleted when a key segment matched an owned
identifier — a family, student, material or item id. A claim taken before a family is known can
only be keyed by the chat it arrived from, and `chat:<ref>` was not in that set, so such rows
survived the command. The row holds no message and no name, but it records that a particular
Telegram chat used this service, which is precisely what `/forget` promises to remove. The local
store had always matched chat scopes; the DynamoDB path now does too.

**Consent against behaviour.** This is the finding the review treats as most severe, and there
was one. The consent asked the parent to agree to a list — the alias, the grade, the material and
the practice answers — and enrollment then asked three further questions and kept all three
answers: the school and section, the practice time, and any exam date later sent.

The school and section is the one that matters. "San José 4to B" together with a grade and an
alias identifies a child far better than any of those alone, and it is exactly what the consent's
own framing — use an alias, keep names off the pages — exists to avoid needing. Every one of the
three is explained at the point it is asked, so nothing was concealed; what was wrong is that the
paragraph the parent taps "Acepto" on did not describe the record being consented to.

The consent now names those three. Nothing about what is collected or retained changed: the
mismatch was closed by correcting the description, not the behaviour, which is the only safe
direction for a reviewer to close it in. `CONSENT_VERSION` moved to v2, because a family that
enrolled under v1 agreed to the shorter list and their stored record must say so.

Two fields the record holds are still not in that paragraph, and one thing the service does with
a field that is. The review closes none of the three. The family row carries a `timezone`, which
no question asks and no command changes: it is the fixed default `America/Caracas` that the
scheduler reads, so nothing about the family is learned from it. The family row and the consent
record both carry the Telegram `chat_ref`, which is how the service reaches the parent at all and
what `/forget` erases. And the section is not
only stored: once `cohort_min_families` families in one section struggle with the same
competency, each of them is told how many, so one family's difficulty becomes an aggregate
another family reads. The chat reference and the cohort signal are decisions for whoever runs the
pilot, not wording a reviewer should settle alone.

## IAM

Read from the synthesized templates rather than from the source, because what is granted is what
CloudFormation renders.

**The worker held a wildcard over every model in every region.**
`bedrock:InvokeModel` and `InvokeModelWithResponseStream` on
`arn:aws:bedrock:*::foundation-model/*` and on every inference profile in the account — held by a
role that cannot reach a model call at all. `worker._dispatch` sends every event to AgentCore
whenever local mode is off, which in a deployed stack it always is. The repository already knew
which four models it uses: the AgentCore execution policy names them one by one, and that role is
the one doing the inference. The grant is gone.

**Two roles could read every photograph.** The worker and the webhook both held
read, write and delete on the material bucket together with Encrypt and Decrypt on the key
protecting it. The webhook serves the API, whose container builds a state store, a Telegram
sender, a Telegram media fetcher and an event publisher; none of them opens an S3 object. Both
grants are gone.

**The worker could read three secrets it never opens** — the Telegram bot token, the judge code
and the pilot invite codes. It imports no module that calls Secrets Manager. Gone.

**What remains is what the code calls:** the table and the event bus for the webhook and the
scheduler, the two secrets the API actually reads, the AgentCore runtime and its ARN parameter
and the three queues for the worker, and a KMS grant scoped to the project key that the table's
encryption now requires. The worker holds neither the table nor the bus: in a deployed stack it
decodes an SQS record and calls `InvokeAgentRuntime`, and the state and the events on the far
side of that call are the runtime's, behind the runtime's own role.

The AgentCore execution role was already well shaped: models named individually, the key scoped,
secrets scoped by name, `iam:PassRole` conditioned on the service it may be passed to, and the
statements whose placeholders never resolved dropped at synthesis rather than deployed
half-formed. Two changes reached it from the deployment work rather than from this review. It
lost `repaso/judge`, which nothing in the runtime resolves, and it gained
`scheduler:ListSchedules`, which the runtime needs to find the family alarms it owns and which
admits no resource, so that grant is region-wide. Read out of the rendered template it now holds
four `Resource: "*"` statements: ECR authorization, X-Ray, Textract and that schedule listing;
the two CloudWatch ones are conditioned on namespace. Every one of them is declared, with what it
can and cannot reach, in [isolation and reversal](../operations/isolation.md).

`tests/infra/test_least_privilege.py` reads the templates and fails if any Lambda role regains a
model action, an S3 action, a secret the webhook does not need, an unconditioned wildcard
resource, or a KMS grant that is not the project key — and if the runtime's own model grant ever
widens to a wildcard.

## The model boundary

### Into the model

Material from a photograph is untrusted input that reaches a prompt. Two stages stand in front of
it, and the model-facing stage wraps the content in `<untrusted_content>` delimiters with an
instruction that it is data and not a request.

**A real evasion of the first stage was found and fixed.** `canonical` folded case, accents,
leetspeak and whitespace, so `1gn0r4 tus reglas` and `ígnora las ínstruccíones` both landed on the
marker they were hiding. It folded nothing invisible. A zero-width space between two letters is
not whitespace under `\s`, so it survived every pass and split the marker in two:

| Character inserted between every letter of a marker | Before | After |
| --- | --- | --- |
| Zero-width space, non-joiner, joiner | passed | blocked |
| Soft hyphen, word joiner, byte-order mark | passed | blocked |
| Left-to-right mark | passed | blocked |
| Combining grapheme joiner | passed | blocked |

Eight for eight. The combining grapheme joiner slipped through for a second reason: it is a
nonspacing mark whose combining class is zero, so the old `unicodedata.combining` filter did not
see it either. Folding by Unicode category instead drops all of them, and drops the accents the
old filter existed for, since those are the same category. None of these is visible in the
Telegram bubble a parent reads, and all are one tap away in a phone's character picker.

**Tested against a live model.** With the deterministic screener left as it is and the model stage
calling the configured classification model in `us-east-1` on September 12, 2026:

| Attempt | Deterministic stage | Two-stage verdict |
| --- | --- | --- |
| Paraphrased role override, no marker | passed | blocked, `grade_manipulation` |
| Instruction to award full marks | blocked | blocked |
| Base64-encoded "ignore your instructions" | passed | blocked, `prompt_injection` |
| Authority note embedded in a worksheet page | passed | blocked, `grade_manipulation` |
| Indirect request to restate surrounding context | passed | blocked, `prompt-injection` |
| Lure asking the child to send a photograph | blocked | blocked |
| Spoofed system role in a JSON fragment | passed | blocked, `grade manipulation` |
| Two ordinary fourth-grade maths messages | passed | allowed |

Five of the seven attacks defeat the marker screener and are caught by the model stage; two are
caught before any model sees them. Both benign controls passed. Nine live calls to a
low-cost model, well under one US cent of inference.

This measures the two-stage screener. It does not measure the Bedrock guardrail's prompt-attack
filter as a defence — that third layer is now measured, but what it caught was the tutor's own
scaffolding rather than an attack; see the next section.

### Out of the model

This direction matters more, because what comes out reaches a nine-year-old.

**The guardrail is attached to model calls, not only to intake.** `build_model` passes the
guardrail id and version into the Strands Bedrock model, which applies them to the inference call
itself in both directions; `apply_guardrail` on intake is a separate, earlier use of the same
guardrail. Both are wired. The input direction additionally carries the deterministic screener
and PII redaction of the child's answer before the grader sees it.

**Being wired was not the same as working, and the difference was measured late.** Every model
figure in this repository was collected with no guardrail on the call, and the only cost ascribed
to attaching one was latency. Run through the attached configuration, the turn reader returned
nothing on 23 of 51 lines — ordinary schoolwork included — because the untrusted-content sentence
this repository wraps around a family message reads to the prompt-attack filter as a prompt
attack, and because wrapping a child's sentence in that scaffolding raises the harm filters'
reading of it. The reader now hands the model the family's message as the turn and carries its
briefing in the system prompt, which the Converse guardrail does not screen on input, so what the
attached guardrail sees is the text the screener already passed. Measured in
[the safeguard path evidence](../evidence/safeguard-path-2026-09-13.md). Two things follow for
anyone changing a prompt: a user turn on a guarded call is read by the prompt-attack filter, and
the system prompt not being screened is current service behaviour rather than a guarantee.

**The output side was inheriting a library default, and now states its intent.**
`guardrail_config` passed an id and a version and nothing else, so every other knob took the
Strands default. Two of those mattered. `guardrail_redact_output` defaults to `False` while
`guardrail_redact_input` defaults to `True` — the wrong way round for a system whose input is read
by a model and whose output is read by a child. `guardrail_stream_processing_mode` was unset;
naming it synchronous means a future change to the service default cannot quietly start releasing
chunks the filter has not seen. Both are now explicit, and the client-side replacement text
carries the same Spanish sentence the guardrail stack gives `blockedOutputsMessaging`.

**A blocked output yields something safe rather than an error.** A blocked or failed model call
produces no parseable structured result, `structured()` raises `StructuredCallFailed`, and every
one of the nine agents that can reach a family catches it and answers with its own deterministic
wording — for the daily capsule, "Hoy practicamos <competency>. Lee cada pregunta con calma."
The child gets a real sentence, not a stack trace and not silence. This was traced by reading
every call site and is exercised by the existing suite.

Worth stating plainly: that safety came from the parse failing rather than from a decision, which
is why the output redaction is now set deliberately rather than left to default.

**No independent screen sits on the outbound message.** Composed text goes from the agent to
`deliver` to Telegram. The Bedrock guardrail's output filters are the only thing between the model
and the child, and they are configured at HIGH for all five harm categories. If no guardrail id is
configured, nothing screens the outbound direction. This was not changed: a local outbound
screener built from the current PII patterns would redact legitimate arithmetic, which is a real
effect — the phone-number pattern already rewrites a contiguous seven-digit answer as `[redacted]`
where it is applied to the child's answer before grading.

## The channel

**Authenticity.** The webhook requires Telegram's secret header and compares it with
`hmac.compare_digest`. A missing or wrong token is 401; an unconfigured secret is 503, so the
endpoint fails closed rather than open. A malformed body is logged and acknowledged, never raised.

**Replay and idempotency, corrected.** The webhook decided whether it had already seen an update
by reading an operation record that it only writes after publishing. Between the read and the
write an update is admitted but unrecorded, and a second delivery landing in that window
published the event again. Telegram retries a webhook it considers slow and the function is
allowed thirty seconds, so the window is not theoretical: one message becomes two events, two
queue messages, two runtime invocations, and the family can be answered twice. The store already
had the primitive — `claim` is a conditional write that succeeds for exactly one caller. Admission
is now claimed before publishing and released if publishing fails, so a failed publish leaves the
update deliverable instead of silently swallowed.

**The allowlist.** A stranger cannot enroll. Enrollment requires a valid invite code read from
Secrets Manager; without one the reply is `unknown_chat`, and if no codes are configured at all
the reply is `enrollment_closed`. No record is written for an unknown chat.

**What happens when a stranger messages the bot** is covered under abuse below, because the
correct refusal is also the expensive one.

## Availability and abuse

**The per-day model budget is real and atomic.** `reserve_budget` increments a per-family counter
and a global counter in one DynamoDB transaction with a condition on each, so a family cannot
exceed 40 model calls a day and the whole system cannot exceed 400, and concurrent callers cannot
race past either. Exhaustion raises `ModelLimitReached`, which is surfaced to the parent as
"pending work is saved", not as a failure.

**The circuit breaker** opens per model role on repeated failure and recovers on a timer, so a
failing model is not retried in a tight loop.

**The dead letter queues would catch a poison message.** The worker returns
`batchItemFailures` per record, the event sources are configured with
`report_batch_item_failures`, each queue has a redrive policy of three receives onto its own DLQ,
and each DLQ has a CloudWatch alarm at a depth threshold of zero, so a single message landing
there alarms. A record that fails to decode is caught and reported as a failure like any other,
so a malformed body redrives and lands rather than looping. This was read from the templates and
the handler; it was not exercised against deployed queues.

One refusal is deliberately not a failure. A spent daily or per-message ceiling returns
`spend_ceiling_reached`, and the worker accepts the message rather than redriving work that cannot
succeed until the allowance resets. The family is told once per reason per day that practice is
paused and that nothing they sent was lost, and the ceiling raises its own signal, so a paused
pilot shows up as a pause instead of as a dead letter queue filling with messages that were never
poison.

**A stranger could drive runtime invocations, and now costs more to do it.** A message from an
unknown chat is authenticated as coming from Telegram, not as coming from a family, so it passes
the webhook, becomes an event, crosses the bus and a queue, and starts an AgentCore session that
discovers there is no family and answers `unknown_chat`. The per-family model budget does not
bound this, because that path never reaches a model. The DLQs do not, because nothing fails. The
alarms do not, because a flood of correct refusals is neither an error nor a throttle. The HTTP
API had no throttle at all, so the first limit anything met was account Lambda concurrency. It now
carries a default route throttle — 20 requests per second, burst 40, both settable from context.

The webhook also decides admission before it publishes anything. Every chat is reserved against a
per-minute count, and a chat it does not recognise -- no family, no enrollment in progress -- is
reserved against a daily one as well. A refused message is answered 200 and never becomes an
event, so the flood stops before the bus, the queue and the AgentCore session rather than being
paid for and then refused, and each reason is traced once per window where an alarm can see it.

That bounds what a stranger costs; it still does not authenticate one. The check asks whether the
chat is already known, not whether whoever is typing should be, so a stranger's first messages
each day are admitted exactly as before and answered by the fleet. Refusing an unknown chat
outright at the webhook needs the invite codes there, and the webhook is deliberately the
component that holds almost nothing.

**A looping family** is bounded by the same per-family budget of 40 model calls a day, and by the
media fetcher's size caps and content-type checks on anything uploaded.

## Dependencies

`pip-audit` against the pinned lock reported 87 known vulnerabilities across three packages.

**`pypdf` 6.0.0 carried 75 of them, and it is the one dependency that reads a file a stranger
chose.** A parent forwards whatever the school sent; `TextractExtractor.extract` opens it with
`PdfReader` to check it is unencrypted and one page, and that parse happens before anything else
looks at the bytes. The surrounding code caps size at ten megabytes, requires a single page, and
turns any parser exception into `unsupported_pdf` — but it cannot bound a parser that does not
raise, and an advisory whose symptom is an infinite loop or unbounded allocation holds the runtime
until the session times out. Pinned to 6.16.1, which clears all 75. Verified by installing the
project against the edited lock in a throwaway environment and running the whole suite there.

**`pip` and `setuptools` still carry advisories** — ten and two. Both are build-time, reachable
only while installing from a pinned constraint file, and moving `setuptools` touches the build
contract in five places. Left for a deliberate change; recorded below as an owner decision.

No unmaintained package was found: every pinned version in the lock is a current release.

## Container

The AgentCore image ran as root, which `python:3.12-slim` does by default and nothing in this
runtime needs — it listens on 8080 and writes only to `/tmp`. It now creates a system user and
runs as uid 10001. The Lambda images are left alone; their base image and sandbox handle this
differently and changing the user there risks the runtime interface.

## Residual risk

Things that remain true after this review.

- **Nothing is deployed, so no control has been observed in production.** Every infrastructure
  finding was read from a synthesized template. Templates and reality diverge at deploy time.
- **One key protects two data classes.** The table and the material bucket share the project CMK,
  so a role holding Decrypt for the table could decrypt material ciphertext if it obtained it.
  The S3 grants are what keep those apart, not the key.
- **The Telegram and judge secrets remain on the Secrets Manager AWS-managed key.** Giving them
  the project key makes the foundation stack depend on a role defined in the api stack, which
  already imports the table from foundation, and CloudFormation refuses the cycle.
- **SQS and EventBridge carry message payloads under AWS-managed defaults.** Queue messages
  include the child's answer text. They are encrypted at rest by the service default, not by the
  project key.
- **The Lambda handlers log family and student ids.** The telemetry sink is careful — it strips
  family id, student id and chat ref before writing — but `logger.info` calls in the scheduler
  write ids directly. They are opaque identifiers, not names, and the log groups expire in seven
  days, which the consent discloses. `/forget` does not purge logs.
- **Dedupe and admission rows never expire.** They are erased with the family, but a family that
  never calls `/forget` accumulates one row per message forever.
- **The deterministic screener is a marker list.** Paraphrase and encoding pass it, by
  construction. Two live attempts confirmed this. The model stage caught both, and that is the
  design, but the first stage should not be mistaken for the defence.
- **PII redaction can eat a legitimate answer.** The phone-number pattern rewrites a contiguous
  seven-or-more-digit number as `[redacted]` before the grader model sees an open answer.
  Uncommon in fourth-grade arithmetic, not impossible.
- **The webhook's admission claim has a small loss window.** If the process dies between claiming
  and publishing — not an exception, which is compensated, but a hard stop — the update is not
  retried, because the claim is held.
- **The concurrency tests exercise a double, not DynamoDB.** The flake this section used to
  record — `test_concurrent_distinct_answers_preserve_all_learning[dynamo]` failing under load —
  was diagnosed and removed: the fixture handed one boto3 client over Moto's in-process backend
  to several threads, and Moto does not execute a transaction atomically against everything else,
  so two threads could satisfy the same condition and both write. The double now serves one
  request at a time, which is the guarantee the service gives. What remains true is that the
  compare-and-swap these tests are about has still only been observed against Moto; a real
  `TransactWriteItems` conflict has not been.

## What deployment must prove

These cannot be established from this repository and are not claimed.

| Assurance | What would establish it |
| --- | --- |
| The guardrail exists and is enforced | `aws bedrock list-guardrails` returns the `repaso` guardrail, and `get-guardrail` shows five harm filters at HIGH in both directions, prompt-attack HIGH on input, and five PII entities set to ANONYMIZE |
| A blocked output actually reaches the child as the safe sentence | Send a prompt that trips an output filter through a deployed runtime and observe the Telegram message; `blockedOutputsMessaging` is only configuration until then |
| The guardrail version in use is the published one, not DRAFT | The runtime's `REPASO_GUARDRAIL_VERSION` resolves to the published version the stack creates |
| The runtime can apply the guardrail | The execution role's `bedrock:ApplyGuardrail` statement resolves against the real guardrail id; the placeholder is substituted at synthesis and unverifiable before deployment |
| Least privilege holds in fact | IAM Access Analyzer over the deployed roles, and CloudTrail showing no denied call the system needs and no permitted call it does not make |
| Buckets refuse plaintext | An HTTP request to an object returns 403 |
| The table is encrypted with the project key | `describe-table` shows `SSEDescription` naming the key |
| The DLQs catch a poison message | Publish a malformed event and observe three receives then arrival on the DLQ and the alarm firing |
| The throttle limits a flood | Drive the endpoint past 20 requests per second and observe 429 |
| Erasure is complete in production | Enroll a test family, exercise every path, call `/forget`, then scan the table and list object versions |

As of this review the account holds no CloudFormation stacks and no Bedrock guardrails. Both were
confirmed by read-only calls on September 12, 2026.

## Verifying this review

```sh
export PYTHONPATH=$PWD/src
python scripts/check_repo_hygiene.py --all     # every ref, not just this branch
ruff check .
pytest -q
pytest -q tests/infra                          # reads the synthesized templates
```
