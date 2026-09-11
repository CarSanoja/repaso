# Evidence register

Two dates. September 6, 2026 is the pre-commit verification after the gap remediation: the
system runs, recovers and packages, entirely on authored model outputs. September 12, 2026 is
the day the model fleet was actually called — 930 live Amazon Bedrock calls counted in
committed ledgers, and one further recording campaign whose ledger stays out of the repository,
every token read from the provider's own usage metadata and priced from the dated table in
`src/repaso/config/pricing.py`.

What changed on September 12 is the kind of claim this repository can make about the models.
Before it, every statement about them was either about shape or about intent. After it, the
routing is measured, the demonstration replays a recording rather than an authored script, one
day of practice has a price, and the grader has been compared against a written label on half
the evaluation set. What did **not** change is the ceiling on all of it: no teacher has
labelled a single case, and no family has used the product. Every quality-shaped number below
is agreement with the person who wrote the answers, or a count of defects the harness itself
planted.

The implementation is committed locally as `08826b26f8df5dbd3a125539666cbf7058f3f9cd` and the
evaluation kit as `42d7096fe349a741ac174f6ec5e00513ec98ae03`. The release manifest records the
original candidate's exact file hashes and base commit. No cloud deployment or publication has
occurred. Historical August figures are not substituted for this evidence.

## Measured

Proportions carry their denominator and a Wilson 95% interval. A count is written as a count.

| Claim | Evidence | What it does and does not establish |
| --- | --- | --- |
| The routing each role uses was measured, not assumed | [Model profile](model-profile-2026-09-12.md), [rows behind it](model-profile-2026-09-12.json) | 489 live calls, $1.176715 from the ledger. Nine schemas against four model ids at eight samples a cell: 284/288 parsed [0.965, 0.995], and every cell is 8/8 [0.676, 1.000] except Claude Haiku 4.5 on `GeneratedBatch` at 5/8 [0.306, 0.863] and Nova Lite at 7/8 [0.529, 0.978]. Two roles moved on that evidence, three did not. Parse rate and latency only — never item quality or grading accuracy. Eight samples is not a rate, and two overlapping intervals are not a separation |
| Four decisions with a defined answer were checked against models, not assumed | [Model profile](model-profile-2026-09-12.md) | 128 live calls, $0.194411. Admitting a clean page, refusing a page carrying a hidden instruction, and ranking the material's own competency first: 8/8 [0.676, 1.000] on all four model ids. Policy agreement 8/8 on three and 7/8 [0.529, 0.978] on Sonnet, and that row is agreement with the deterministic action, not truth. Four questions, one fixture each |
| One day of practice for one student has a measured price | [Model profile](model-profile-2026-09-12.md), `scripts/run_live_journey.py` | $0.162886 over 29 live calls, all accepted, on the routing that ships. One synthetic family, one day. The student-month and thirty-family figures beside it are arithmetic on that single journey, labelled as such in the artifact, and are not an observed cost; the scenario's follow-up days are authored playback and are priced nowhere |
| Every fallback a failed model call takes has been driven | `tests/agents/test_ingest_fallbacks.py`, `tests/agents/test_practice_fallbacks.py` | 27 tests: nine agent call sites times three injected provider failures — throttle, deadline, malformed payload — each asserting what the family is left with. Injected failures, not observed ones. Two of the nine tell the family its photograph was the problem when the provider was; the profile records that and does not fix it |
| The demonstration replays model outputs that were recorded, not written | [Recorded journey](demo-cassette-recording-2026-09-12.json), `src/repaso/simulator/cassettes/demo_fracciones.provenance.json` | 31 live calls, 31 answered, $0.164908 from the ledger, one entry per call, replayed to the last entry with none left over. Day one only: the days after it still play authored payloads. A replay is not a live run and one recording is not a rate. Two recordings were made on this routing and the shipped one was chosen because the other left two of the journey's stages unexercised — the artifact says so and reports what the discarded run graded |
| Both complete family choices have a consequence | [Teacher-note run](journey-teacher-note.json), [reduced-load run](journey-reduce-load.json) | 24/24 and 23/23 assertions over seven stages. Day one replays the recording above; the continuation days are authored. Synthetic family, accelerated time, local delivery |
| The development half of the evaluation set has real predictions | [Development run](answer-evaluation-development-2026-09-12.json), [what it measured](answer-evaluation-development-2026-09-12.md) | 30 development cases, 25 live judge calls, 5 stopped by the local screener before any call, 0 errors, $0.1465 from the ledger. Agreement with **author-proposed** labels: grades 18/18 [0.824, 1.000] on automatic decisions, review decisions 24/30 [0.627, 0.905], and 0 false automatic-correct of 8 called correct — a rate of 0.000 whose interval reaches [0.000, 0.324], which is not a safety result. Thirty cases are 18 distinct answers to 5 questions; three categories are one answer text repeated five times. No teacher has labelled any case, so this is not accuracy. The held-out half was not opened |
| The confidence threshold is chosen and frozen on the development half | [Threshold sweep](answer-evaluation-development-2026-09-12.json), [criterion and freeze](answer-evaluation-development-2026-09-12.md) | Swept 0.70–1.00 in 31 steps on the 30 development cases before any held-out case. 0.85 kept, on a written criterion: move only for a measured reduction in false automatic-correct. That error is 0 at every threshold, so the sweep cannot rank candidates and 0.85 was kept for want of evidence to move it. It sits exactly on a mass point — 8 of 25 calls reported 0.85 — and remains a product rule, not a calibrated probability, fitted to one model id, one prompt version, one day |
| The advisory answerability probe does not pay for its call | [Ablation analysis](probe-ablation-2026-09-12.md), [per-arm report](probe-ablation-2026-09-12.json), [270 capture rows](../../evaluation/ablation_observations.csv) | 30 frozen items, three option orders, 90 decisions an arm, 308 live calls, $1.2713 from the ledger. The probe changed 0 of 90 decisions — by construction it cannot — and matched the key on 1/24 clued decisions [0.007, 0.202] against 8/66 unclued [0.063, 0.221]. Labels are **planted defects known by construction**, not teacher labels: planted rejection 34/36 [0.819, 0.985] and unplanted retention 20/54 [0.254, 0.504] are about plants, never about whether a question is good. The critic agrees with itself on 29 of 30 immediate repeats [0.833, 0.994], so it moves on its own by more than the probe moves it |
| Bedrock answered on September 12 and every configured schema parsed | [Conformance report](live-conformance-2026-09-12.json) | 27 live calls at three samples a schema across all five roles, 27/27 parsed [0.875, 1.000]; 28,497 input and 6,046 output tokens, and p50 and p95 latency a role. This run predates the per-call ledger, so its $0.1444 is an **estimate** from the dated table and is excluded from every measured total on this page. Twenty-seven probe calls say nothing about sustained throughput under a pilot's load, and nothing here is a deployment, a family journey or a quality result |
| Every model call is measured and priced from what the provider reported | [Live harness run](live-model-harness-2026-09-12.json) | 45 live calls, $0.240946 from the ledger, 40/45 payloads accepted [0.765, 0.952]. One run, one day; not a quality or family measurement |
| Every schema the fleet asks a model to fill is filled | [Schema conformance](live-schema-conformance.json) | 271 live calls over nine schemas and four model ids: 142/153 parsed against the schemas as they stood, 82/82 against the revised ones, 35/36 [0.858, 0.995] through the repository's own live tier. Payload shape only, never item quality. This run predates the per-call ledger, so its $1.1203 is an **estimate** and is excluded from every measured total on this page; the one revised-schema rejection is recorded and unexplained |
| The teardown planner selects nothing that exists in the account today | [Dry run](teardown-dry-run.json), [isolation and reversal](../operations/isolation.md) | One read-only run against the authorized account: discovery is bound to the `repaso` prefix at the API call, returned zero stacks, buckets, secrets and log groups, and produced an empty plan. A separate census counted the 6 buckets, 9 secrets, 13 log groups, 2 functions and 1 table the account holds; those 31 were never candidates, and the refusal tally over them was worked by hand, not printed by the planner. A plan is not a removal: nothing was deleted, here or anywhere |
| A new printed Spanish page is recognized outside the cassette | [Actual OCR result](live-ocr.json), [synthetic input](printed-synthetic-page.png) | One actual Textract request on September 6; no embedded text; confidence 0.9957223510742188. One page. Not an end-to-end tutor result and not a handwriting result |
| Complete transport recovery is exercised | `tests/integration/test_complete_transport.py`; [verification summary](verification-2026-09-06.json) | Ten complete runs through production adapters with Moto AWS and substituted remote AgentCore/Telegram boundaries; half inject failures; all replay webhooks and queue records |
| Fourteen-day continuity passes the scenario gates | [Clock report](clock-14-days.json) | 30 synthetic students, 420 local sessions, 1,037 responses; nine gates pass. Not retention and not learning measured with families |
| ARM64 containers can start and serve application routes | [HTTP smoke report](container-smoke.json) | AgentCore `/ping` and a valid daily close; Lambda health, assets, login and a 23-check judge journey; local mode, without AWS inference |
| Package includes working assets and scenario data | `scripts/check_installed_package.py`; verification summary | Wheel installed into an empty environment and run from `/private/tmp`; both complete journeys and HTTP/assets pass |
| A live inference check on September 6 returned no successful call | [Access check](live-inference-access.json) | Four short actual calls, all throttled. Superseded by the September 12 campaigns, which completed theirs |

## Not done

Nothing here is marked complete because a local file exists. Each row says what would close it.

| Gate | State | What would close it |
| --- | --- | --- |
| Independent teacher labels | Not started. `evaluation/teacher_labels.jsonl` is empty and `independent_reviewer` is `none` on all 270 ablation rows | A teacher completing the blind file. Until then the development run reports agreement and not accuracy, and the ablation reports planted defects and not question quality |
| Held-out half of the evaluation set | Deliberately not collected or scored | A run at the frozen 0.85 on the 30 held-out cases, reported separately from the development figures |
| Calibration of the grader's confidence | Not attempted | Enough labelled decisions to separate the band where a person should look. The grader reports six distinct confidences here, and the answers it should have held sit in the same 0.82–0.85 band as the ones it graded correctly |
| A false-automatic-correct rate | Not established | About 74 clean automatic correct decisions would put the upper bound under 5%. Eight bound it at 32.4% |
| Observed families | None. No participant has used the product | A pilot. The [kit](../pilot/README.md) has an empty observation template and an analyzer that preserves missing observations; no participants and no savings are reported |
| Teacher feedback on generated questions | None | A teacher reading the items, keys and rubrics before a family pilot |
| Cloud deployment and scheduled delivery | Not done | A deployed stack delivering on a real schedule. The [deployment checklist](../../deploy/README.md) records what remains |
| The ablation's recommendation | Not acted on | The advisory probe is still called in `src/repaso/core/orchestration/ingest_graph.py`. Disabling it is a product decision, left to the maintainer, on the strength of one 30-item construction-labelled run |
| The two misattributed failure messages | Recorded, not fixed | When the screener or generator call fails, the family is told its photograph was the problem. The profile names both and does not repair them |
| The missing `rationale` in generated batches | Diagnosed, not repaired | It is the only conformance failure in 288 calls, always a later item and never the first, which points at the prompt. Changing the prompt would invalidate the profile's generate numbers, so it needs a run of its own |
| A rejected call that a replay can reproduce | Not done | The recorder writes an entry only for an answered call, so a cassette cannot replay a rejection. One call in 32 was lost that way during the shipped recording's campaign |
| An observed removal | Not done. Every removal so far has been planned and none executed | One run of `scripts/teardown.py` against a deployed stack, deleting the stacks, emptying the buckets and force-deleting the secrets it selects. The dry run shows only that discovery stays inside the `repaso` prefix and chose nothing |
| Public repository, hosted demo, video, articles, submission identity | Not done | Publication |

## What the live campaigns cost

Read from the per-call ledgers each campaign wrote, priced from the dated table.

| Campaign | Live calls | Measured |
| --- | --- | --- |
| Model profile — conformance matrix, decision probe, deadline probe, pipeline smoke, two journeys | 489 | $1.1767 |
| Probe ablation — item generation and three arms | 308 | $1.2713 |
| Demonstration cassette — two recordings on the routing that ships | 63 | $0.3283 |
| Demonstration cassette — four earlier recordings and 24 diagnostic calls, on the routing before it | not counted | $1.0216 |
| Live harness run | 45 | $0.2409 |
| Answer evaluation, development half | 25 | $0.1465 |
| **Total** | **930 counted** | **$4.1854** |

Four boundaries on that total. The profile's figure is a **floor**: three calls abandoned at a
deliberate deadline reported no usage at all, so the ledger prices them at zero, and what the
provider billed for the generations it had already started is not visible from the client. The
earlier cassette campaign's ledgers are written to `private/` and are not committed, so its
dollars are a reading from a ledger this repository does not carry and its call count is not
recoverable here; the two recordings made on the shipped routing are 32 and 31 calls, and the
shipped one's own $0.164908 is in its artifact. The whole column is quoted to four places
because that coarsest line is. And the 271-call schema conformance run is excluded entirely,
because its $1.1203 is an estimate rather than a ledger reading.

## Claim boundaries

The ten transport runs emulate EventBridge, SQS, DynamoDB, S3 and Scheduler. They call the real
adapters and graph handlers, replace the AgentCore service boundary with a local dispatch, and
mock Telegram HTTP responses. They cover publication/send failures, duplicate callbacks/events,
adult decisions, schedule pause/resume and erase. They are **not ten deployed live journeys**.

Application traces and the per-call ledger distinguish live, replayed and simulated origin, and
report tokens only when the provider supplied them: a call whose usage was never reported
carries no usage and no cost rather than zeros, and a report over such a ledger prints "not
reported". Prices come from the dated table in `config/pricing.py`, checked on September 12,
2026 against the AWS Price List API and the published Amazon Bedrock rates; they exclude
infrastructure, storage, delivery, text extraction and human time, and a cache write is charged
at the five-minute rate because the usage the harness reads does not say which time-to-live was
used. The demonstration cassette's usage numbers are the provider's own; a replayed run is
labelled as a replay wherever it is reported, and replaying a recording spends nothing.

Agreement is not accuracy. Where a figure compares the model with a label, the label is named:
`author-proposed` on the evaluation set, `construction` on the ablation. Neither is a teacher.
Self-reported model confidence is not a calibrated probability. The options-only answerability
probe is advisory and vetoes nothing. A shared section signal is experimental and does not
establish formal anonymity.

DynamoDB transaction tests and local WAL tests cover duplicate/conflicting learning effects.
Telegram delivery remains at least once when acknowledgment is lost. Family deletion covers
active records and S3 versions; retention of logs, backups and Telegram history is described in
the consent.
