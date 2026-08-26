# Self-learning architecture — memories that update and challenge each other

> Adversarial ML-research review commissioned 2026-08-20 against the demo-clock
> benchmark and the frozen architecture. Produced by an external-reviewer persona
> with full read access to the source. Tags: [FREEZE] = shippable before Sep 3;
> [ROADMAP] = post-hackathon design.

# Part 2 — Self-learning architecture: memories that update AND challenge each other

## 2.0 The thesis, and the invariant that keeps it safe

The demo-clock report's own *Honest read* concedes the central problem but understates it. The real shape of it is arithmetic:

**The harness exposes roughly 27 free constants. The benchmark contains 17 planted interrupts.** There are more tunable knobs than there are events to fit them on, and the report presents a single point in that 27-dimensional space, chosen after two of its coordinates (`escalation_min_samples` 5→8, cohort evidence guard) were moved *because the run failed*, then re-ran the same seed and reported 8/8. That is not a benchmark result; it is a fixed point of an optimization whose training set and test set are the same object.

Worse, bug #5 in the report is the tell: *"three archetypes sat on the struggle boundary → abilities recalibrated away from the threshold."* The evaluation removed every student near the decision boundary and then reported perfect classification. Look at the profiles: the "should fire" group sits at ability 0.20–0.25, the "should not fire" group at 0.65–0.75, and `STRUGGLING_CEILING` is 0.40. **Nothing in the cohort lives between 0.40 and 0.55.** Zero false interrupts across 420 student-days is not evidence of a sharp detector; it is evidence of a chasm that was widened on purpose.

Self-learning is the only escape from this — but naive self-learning makes it *worse*, faster: it is tuning-on-the-test with a cron schedule. So every learning block below obeys one invariant, and I would put it in the README verbatim:

> **No memory updates itself without a named adversary, a held-out gate, an anti-gaming validator, and an append-only promotion record that can be reversed with one write.**

This is also how self-learning stays compatible with the frozen philosophy in `private/architecture.md` §5. The deterministic algorithms never learn their *math*. They learn their *constants*, and constants become versioned, hashed, auditable data. The code a parent's lawyer would read stays byte-stable; what changes is a row with a provenance trail.

---

## 2.1 Block L0 — The enabling refactor: constants become versioned data

Nothing in this part is buildable until this exists. The tunable constants are currently scattered as module-level literals across six files:

| File | Constants |
|---|---|
| `core/harness/mastery.py` | `EMA_ALPHA`, `MIN_ATTEMPTS_FOR_LEVEL`, `STRUGGLING_CEILING`, `DEVELOPING_CEILING`, `SOLID_CEILING` |
| `core/harness/escalation_triggers.py` | `DEFAULT_COOLDOWN_DAYS`, `DEFAULT_SILENT_DAYS`, `DEFAULT_MIN_ACTIVE_DAYS`, `FAST_GUESS_RATIO` |
| `core/harness/psychometrics.py` | `MIN_OBSERVATIONS`, `P_CEILING`, `P_FLOOR`, `DISCRIMINATION_FLOOR` |
| `core/orchestration/quality_graph.py` | `COHORT_WINDOW_DAYS`, `REWORK_MAX`, `RETIREMENT_MIN_ATTEMPTS` |
| `agents/adaptation_policy.py` | `RAISE_ACCURACY`, `RAISE_STREAK`, `LOWER_ACCURACY` |
| `core/harness/sm2.py` | `MIN_EASE`, `FIRST_INTERVALS`, `FAILURE_QUALITY_THRESHOLD`, latency multipliers in `grade_to_quality` |
| `config/settings.py` | `cohort_min_samples`, `grader_confidence_threshold`, `escalation_min_samples`, … |

**Repair:** one frozen `PolicyConstants` Pydantic model, injected through `Services`, with `config_hash = sha256(canonical_json)`. Every `Escalation`, `GradeResult`, and item-retirement decision carries the hash. "Why were we interrupted?" then resolves deterministically to a trigger vector **plus** the exact constants in force **plus** the sweep that promoted them.

**One latent bug to fix in the same pass:** `adaptation_policy.build_signals` passes the *same* `min_samples` to `struggle_trigger` and to `fast_guess_flag`. Sweeping `escalation_min_samples` silently moves the fast-guessing detector. Two unrelated thresholds are welded together, which makes any calibration result uninterpretable. Decouple before sweeping (30 min).

**[FREEZE — 3h]**

---

## 2.2 Block L1 — Replay Calibrator: counterfactual threshold calibration

| | |
|---|---|
| **Learns** | `escalation_min_samples`, `cooldown_days`, `silent_days`, `min_active_days`, `cohort_min_families` (k-floor), `grader_confidence_threshold`, `RETIREMENT_MIN_ATTEMPTS`, mastery ceilings |
| **Memory updated** | `ConfigVersion` record (DynamoDB `pk=POLICY#core, sk=V#<n>`, plus an `ACTIVE` pointer) |
| **Adversary** | Adversarial cohort search (§2.2.4) + held-out seed families |
| **Gate** | Dominance on held-out seeds, paired-bootstrap CI on the delta excluding 0, recall floor, **plateau interiority** |
| **Anti-gaming** | Integer-only human-readable candidates; recall floor; test-seed hash published; test seeds run once per release |
| **AWS** | S3 (tapes + sweep results, Athena-queryable), DynamoDB (config versions), EventBridge rule (nightly re-sweep as pilot data grows). No Bedrock — this loop has no LLM in it, which is precisely why it is auditable |

### 2.2.1 Two replay tiers, and the honest difference between them

Deterministic replay is already there (`SimClock` + seeded responses + full state store), so counterfactuals are cheap — but not uniformly cheap, and conflating the two tiers is how people ship a calibration that lies.

- **Tier-A (tape replay, open loop).** Record an event tape: for every response, `(student, competency, item, difficulty, correct, latency, day, mastery_state_before, daily_counts_before)`. The trigger functions in `escalation_triggers.py` are pure functions over exactly this. Replaying a 5×5×5×5 grid of gate parameters over 1,062 events is sub-second per candidate. Use it to prune thousands of candidates.
- **Tier-B (full replay, closed loop).** Tier-A is an *approximation* and the report should say so: when `struggle` fires, `decide()` short-circuits the adaptation action, so firing genuinely changes the subsequent item stream. Tier-A is valid only within a short horizon after a divergence. So: Tier-A prunes, Tier-B confirms. A full run is 14.1 s; 200 finalist runs is 47 minutes on one core, ~6 minutes across 8 processes. **Counterfactual calibration for this system costs single-digit minutes.** There is no excuse for reporting a point estimate.

### 2.2.2 The metric that replaces "8/8"

Binary per-student ledger checks are the wrong instrument. Report instead:

1. **Operating characteristic**: firing rate as a function of *true latent ability* (the simulator knows `ability_on_day`), sampled densely across [0.25, 0.65]. From the curve you read the *effective* threshold, the **transition width** (how wide the ambiguous band is), and whether the detector is sharp or mushy. This is the direct repair for "abilities recalibrated away from the threshold": you can no longer report a result by evacuating the boundary, because the boundary *is* the result.
2. **Detection delay**: days between the first day latent ability crosses the concern line and the day the alert fires. A trigger with perfect precision and a 9-day lag is useless to a parent.
3. **False alarms per family-week** — not per 420 student-days. That is the unit a school feels.
4. **Interrupt burden**: total interrupts per family per month, reported as a cost alongside recall (see §2.7a).

### 2.2.3 Held-out seeds that are actually held out

`build_cohort(services, now)` takes **no seed**. `COHORT_MIX` is a hardcoded 10/4/3/2/5/3/2/1; sections are assigned by a fixed rule; `dropout_day=6` and injection on days 2–3 are constants. Today, changing the seed only re-rolls Bernoulli draws for individual responses. The *structure* — who is low-ability, who goes silent, when — is identical across every "different seed." The report's pending "multiple seeds" work will therefore produce near-identical runs and will be mistaken for robustness.

**Repair:** `build_cohort(services, now, rng)` sampling cohort size, archetype mix (Dirichlet over the mix), per-student profile jitter (±15% on `base_ability`, `learning_rate`, `forgetting_rate`, `response_rate`), section assignment, dropout day, and injection day. Then split: seeds `1..40` are the training family (sweeps may look at them freely), seeds `41..80` are the test family, their hash committed, run once per release. Any number reported in the README comes from the test family or it does not go in the README.

**[FREEZE — 3h for the seeded cohort generator; 4h for the operating-characteristic sweep; 9h for the tape recorder + grid + bootstrap CI + plateau check]**

### 2.2.4 The adversary: an optimizer whose job is to embarrass you

The stated sin — *"the archetypes were designed by the same person who designed the triggers"* — is not repaired by more archetypes from the same person. It is repaired by an **objective function that rewards breaking the triggers**. Given a candidate constant vector, run a bounded random/CMA-ES search over `ArchetypeProfile` fields, constrained to a plausibility box (ability ∈ [0,1], response rate ≥ 0.5, learning rate ≤ 0.15 — later a prior fit on pilot data), maximizing either false alarms or missed detections. Publish the **worst cohort found**, not only the designed one. A README line like *"under adversarial cohort search within plausibility bounds, worst-case false-alarm rate is 0.4 per family-week"* is worth ten times more to a judge than 8/8.

**[FREEZE if time — 4h; otherwise ROADMAP]**

### 2.2.5 The gate: plateau, not peak

A candidate is promoted only if:

- it **dominates** the incumbent on the held-out seed family (recall ≥, false alarms ≤, delay ≤), with the paired-bootstrap 95% CI on each delta excluding 0;
- it is **non-inferior** on the adversarial suite;
- **its ±1 neighbours also pass.** A parameter that only works at exactly 8 and fails at 7 and 9 is fitted noise, not a threshold. Apply this retroactively to the `5 → 8` change already shipped: if 8 is a spike and not a plateau, that "fix" is a lucky draw and must be reported as such.

**Anti-gaming for this block specifically:** enforce a hard recall floor (a gate that never fires trivially achieves zero false alarms — the degenerate optimum, and the one an unconstrained sweep will find); restrict the search to integers a human can say out loud (no 7.3-day cooldowns); require every promoted constant to be expressible in one sentence in the parent-facing evidence text.

---

## 2.3 Block L2 — Mastery Duel: EMA vs a BKT-style challenger, shadow-scored

| | |
|---|---|
| **Learns** | Which learner model predicts the next response better, per student |
| **Memory updated** | `pk=STUDENT#<id>, sk=MASTERY_MODEL#active` pointer + rolling scores (DynamoDB); prediction log (S3) |
| **Adversary** | Each other, plus a **null baseline** (per-student base rate) that both must beat |
| **Gate** | Rolling Brier improvement ≥ δ over W ≥ 30 responses, sustained H consecutive evaluations; asymmetric demotion band |
| **Anti-gaming** | Strict feature cut-off at item-delivery time; leakage detector; challenger must not increase interrupt burden at fixed recall |
| **AWS** | DynamoDB (pointer + rolling stats — analytic state, per the L3 tier in `architecture.md`); S3 (daily prediction partitions). **Not** AgentCore Memory: that tier is for conversational memory, and putting scoring data there destroys the auditability split |

### What is actually wrong with the incumbent

`update_mastery` is a fine 20-line EMA and a poor learner model:

- `prior = state.ema_accuracy if state.attempts else outcome` → after the first attempt, `ema == outcome` exactly (0.0 or 1.0). `MIN_ATTEMPTS_FOR_LEVEL = 3` papers over it, but the estimator is violently reactive early — exactly when the struggle trigger's evidence gate is deciding a child's fate.
- `last_practiced_at` is stored and **never used in the update**. The model has no notion of decay, while the SM-2 scheduler next to it is entirely about time. Two components disagree about whether time exists.
- No difficulty conditioning: a miss on a difficulty-5 item costs the same as a miss on a difficulty-1 item, though `Item.difficulty` is right there.
- **No uncertainty.** This is the important one. Because EMA returns a point estimate, the escalation gate is forced to proxy confidence with `attempts >= 8` — a magic integer standing in for a posterior width. The deep repair is to replace `attempts ≥ min_samples` with `P(mastery < θ) > q`. That converts a hand-tuned count into a calibrated statement that self-adjusts with evidence quality, and it is *more* auditable, not less: `q` is a stated risk tolerance, `8` is a story about one seed.

### Shadow scoring, done without leaking

Every delivered item is a prediction task. **Before** the answer arrives, each model emits `p(correct)`; the prediction is persisted with a `predicted_at` that precedes `received_at`. Score with Brier, log-loss, ECE (10 reliability bins), and AUC — against two floors that must be beaten: global base rate and **per-student base rate**. If the BKT challenger cannot beat a per-student base rate, it is ornament and should be said so publicly.

### Promotion with hysteresis, per student

Promote the challenger for a student when its rolling Brier beats the incumbent by δ over the last W ≥ 30 responses **and** has done so for H consecutive daily evaluations; demote at a *wider* margin. Asymmetric bands stop students flapping between mastery models mid-week. Every switch writes a ledger row with the numbers at switch time, so a parent-facing explanation always resolves to a specific model version.

**Critical coupling:** you cannot feed a BKT posterior into ceilings tuned for an EMA. Promote **(model, level-calibration map)** as an atomic pair, with the calibration map fit only on training seeds / pilot-train data.

### Honest scoping

Fitting BKT's four parameters by EM at 30 students × 14 days is wishful. Use bounded literature priors (slip ≤ 0.15, guess ≤ 1/n_options for MCQ) per competency and revisit at pilot scale. And note the split in value: **the shadow-scoring harness is worth more than BKT itself** — once two models can be scored head-to-head on next-response prediction, every future modelling claim in this repo becomes falsifiable.

**[FREEZE — 4h for the shadow-scoring harness] · [ROADMAP / stretch — 4h for the BKT challenger]**

---

## 2.4 Block L3 — Item ecosystem coevolution: generator ↔ critic ↔ probe, psychometrics as referee

| | |
|---|---|
| **Learns** | Which items measure anything; which generation prompts produce measurable items |
| **Memory updated** | `pk=ITEM#<id>, sk=STATS#<window>`; retirement ledger; regeneration queue |
| **Adversary** | Answerability Probe ensemble + the new **Misconception Probe** + a never-retired golden item set |
| **Gate** | Two-strikes retirement across independent windows; probation before an item can carry weight |
| **Anti-gaming** | Generator blinded to the retired item's response distribution; golden set immune to retirement; weekly retirement budget cap |
| **AWS** | DynamoDB (item stats/status), EventBridge (retire → regenerate → ingest graph), **Bedrock batch inference** (overnight regeneration of a backlog — no latency requirement, roughly half the on-demand cost), S3 (candidate pool) |

### The referee is currently not honest about n

Three concrete defects in `psychometrics.py` / `item_optimizer.py`:

1. **Part-whole contamination.** `student_totals()` in `item_optimizer.py` computes each student's total score over *all* grades including the item being evaluated, then correlates the item against that total. Standard psychometrics requires the **corrected item-total correlation** (exclude the item from the total). At the small per-student n here the inflation is not marginal. *1h fix.*
2. **Discrimination at n=8 is noise.** Point-biserial SE ≈ 1/√(n−3) ≈ 0.45 at n=8. Against `DISCRIMINATION_FLOOR = 0.15`, a genuinely good item with true r = 0.4 measures below the floor roughly a quarter of the time. Gate the discrimination branch at n ≥ 25 and say plainly in the README: *at pilot scale, discrimination is not measurable.*
3. **p-value retirement fires on luck.** With `P_FLOOR = 0.05` and n=8, a legitimately hard item with true p = 0.25 returns all-wrong with probability 0.75⁸ ≈ 10% — and it is re-evaluated every single day. This is why **20 of 84 items (24% of the bank) were retired in 14 days**. The tournament is chewing a quarter of the item bank on noise-level evidence, and the report presents that number as a feature.

**Repair (freeze-sized):** Wilson intervals instead of point estimates, plus a **two-strikes rule** — flag on the point estimate, retire only on confirmation in an *independent* subsequent window. Cheap, no large-n requirement, and it collapses the false-retirement rate. Add a weekly retirement budget cap (e.g. ≤ 5% of active bank) as a circuit breaker against bank collapse.

### Coevolution: retirement reasons must be typed and must flow backwards

Retirement is currently a boolean. Make it a typed `RetirementReason` — `TOO_EASY`, `TOO_HARD`, `NON_DISCRIMINATING`, `AMBIGUOUS_BY_QUARANTINE_RATE`, `BLIND_PASS` — and feed it into (a) the Item Generator prompt as an explicit constraint ("the previous item at this competency was retired for X; target difficulty band Y and misconception Z"), and (b) the Item Critic's rubric weights. `Provenance.prompt_version` already exists, so every regenerated item is attributable to the prompt that produced it, which makes L4's tournaments measurable on *downstream psychometrics*, not just on rubric scores.

### A new adversary worth naming in the Devpost

The Answerability Probe asks: *can a student answer without the material?* Add its mirror, the **Misconception Probe**: a simulated student who *holds the known misconception* (`MISCONCEPTIONS` in `archetypes.py`) must answer the item **wrong**. If the misconception-holder gets it right, the distractors do not discriminate the misconception, and the item cannot detect the very error it was written to detect. This is cheap, entirely offline, philosophically consistent (a deterministic adversary refereeing a generated artefact), and it is a genuinely novel validator — a better innovation headline than the Answerability Probe alone.

Also: run the Answerability Probe as an **ensemble** (k samples at temperature) and record a *blind-pass rate*, not a single boolean. A one-shot probe is a coin flip dressed as a gate.

**[FREEZE — 6h: corrected item-total 1h, Wilson + two-strikes + budget cap 2h, typed reasons + prompt feedback 3h] · [FREEZE if time — 3h Misconception Probe] · [ROADMAP — probation status, Bedrock-batch regeneration backlog]**

---

## 2.5 Block L4 — Prompt-variant tournaments fed by human labels (gradesync `Evolve`, ported)

| | |
|---|---|
| **Learns** | Grader / item-generator / escalation-composer prompts |
| **Memory updated** | Prompt registry `pk=PROMPT#<agent>, sk=V#<n>` + `ACTIVE` pointer; calibration corpus in S3 |
| **Adversary** | Human ground truth (quarantine decisions + golden set) + the anti-gaming validator |
| **Gate** | Bounded convergence loop; paired-bootstrap improvement on the held-out split; non-regression **per stratum**; human sign-off for any child-facing text |
| **Anti-gaming** | Variance collapse, constant outputs, ground-truth contact (n-gram overlap between candidate prompt and calibration items), **quarantine-rate band** |
| **AWS** | S3 with **Object Lock on the test/golden partitions** (a real control, not a gesture), **Bedrock batch inference** for candidate scoring, DynamoDB registry, EventBridge weekly schedule |

The gradesync pattern ports cleanly: convergence loops of tournaments, candidates re-scored against the same human ground-truth calibration set, anti-gaming validator, promote the best accepted mutation, stop on marginal improvement or cycle budget. What Repaso adds is that **its ground truth is already flowing and free**: every quarantine a parent approves or rejects is a human label on the grader. Today that decision is stored as a `QuarantineStatus` with an untyped `payload: dict[str, Any]` — the machine's own prediction is not reliably persisted next to the human verdict, which means the labels currently being generated are worth much less than they should be. Fixing that is §2.6, and it is urgent.

Three honest caveats that must be designed around, not hand-waved:

1. **Quarantine labels are a biased sample** — they are, by construction, exactly the low-confidence cases. A grader prompt optimized only on them will regress on the confident majority. Calibration set = quarantine labels (hard stratum) **+ a golden set** of ~60 stratified responses labeled by a teacher, including easy ones. Metrics reported per stratum; promotion requires non-regression on **both**.
2. **Parents are approval-biased** — approving means their child gets credit. For a random 10% of quarantines, present the **blind** version (no proposed grade shown). This de-biases the labels and simultaneously yields an inter-rater agreement estimate for free. Call it **blind audit sampling**; record `rater_role` and weight teacher labels above parent labels.
3. **The 0.85 gate is currently unmeasured.** The entire "never guess" guarantee rests on the grader's `confidence` being meaningful, and in the offline benchmark that number is a scripted constant (0.92 / 0.3 by construction). The single highest-value measurement available once Bedrock unthrottles is the **ECE of grader confidence against human labels**. If confidence is uncalibrated, the confidence gate is theatre and the architecture's third guarantee is unbacked. Measure it before you claim it.

Metrics: QWK and MAE on `rubric_points` (0–2 ordinal — QWK is the right instrument, same as gradesync), plus cost-asymmetric rates (false-credit is worse than false-quarantine), plus the quarantine-rate band as an operational constraint (a candidate that quarantines 40% of answers is useless even if it is accurate).

**[FREEZE — 5h: label capture + blind audit sampling + golden set + offline scorer with QWK/MAE/ECE, then run one *manual* tournament with 4 hand-written variants when Bedrock returns] · [ROADMAP — automated mutation + convergence loop + Bedrock batch, ~20h]**

---

## 2.6 Block L5 — The label flywheel schema: the exact tuples to persist NOW

**Build this first.** Every other block in this part can be built after September 3. This one cannot: signal not captured during the pilot is gone forever. It is the only irreversible item on the list.

Six append-only record types, all carrying `schema_version`, `run_id`, `seed_or_pilot`, `config_hash`, `prompt_version`, `clock_now`, `emitted_at`:

1. **`PredictionRecord`** — written **before** the answer arrives (otherwise leakage): `student_id, competency_id, item_id, item_difficulty, item_kind, model_id, model_version, p_correct, mastery_snapshot{ema, attempts, correct, streak, level}, spaced_snapshot{interval_days, ease, repetitions, lapses, days_overdue}, delivered_at, predicted_at`.
2. **`OutcomeRecord`** — `response_id, student_id, item_id, text_hash, text_length, lang, correct, rubric_points, latency_seconds, graded_by, confidence, quarantined, evidence_ref, graded_at`. **Hash, never raw child text** — the learning corpus must not become the place where the COPPA guarantee leaks.
3. **`HumanLabelRecord`** (the gold) — `quarantine_id | response_id, rater_role, blind, label_correct, label_rubric_points, machine_correct, machine_rubric_points, machine_confidence, agreement, time_to_decision, decided_at`. This is the tuple that does not exist today and that L4 is impossible without.
4. **`InterruptRecord`** — `escalation_id, kind, student_id, family_id, trigger_input_vector` (the *exact* `MasteryState` / daily counts the gate saw), `config_hash, fired_at, delivered_at, parent_action (chosen_option | ignored | expired), time_to_action`, and — the field that matters most — **`followup_delta`**: the student's mastery change on that competency over the next 14 days, against matched non-interrupted student-competencies. That is the only path to ever answering *does interrupting help?*, and it costs nothing to collect.
5. **`ItemStatRecord`** — `item_id, window, n, p_value, wilson_low, wilson_high, corrected_discrimination, blind_pass_rate, misconception_pass_rate, quarantine_rate, retirement_reason, generated_from (parent item id), prompt_version, generation_cost_tokens`.
6. **`ConfigVersionRecord`** — `config_hash, full constant vector, derivation {sweep_id, train_seed_hash, test_seed_hash, metric deltas + CIs}, promoted_by, promoted_at, rollback_of`. Every `InterruptRecord` references it. This closes the audit chain end to end.

**Plus the one everyone forgets: `NearMissRecord`.** Log every `(student, day)` where a trigger *almost* fired, with the margin. Logging only positives is the classic flywheel-killer — without negatives you can never estimate precision or recall on real pilot data, and the pilot is the only external check the report admits to having. Cheap, and it converts the pilot from an anecdote generator into a labeled dataset.

**Storage:** S3 is the corpus of record — daily JSONL partitions `s3://…/learning/dt=YYYY-MM-DD/kind=<type>/`, Athena-queryable, immutable, Object Lock on test/golden partitions. DynamoDB holds only what needs point lookup (config versions, active pointers, human labels), with `gsi1` on student. Zero-code path if you want it: DynamoDB Streams → Firehose → S3. Local mode reuses the existing `LocalTelemetrySink` pattern — same interface, JSONL on disk, no credentials.

**[FREEZE — 6h: schemas 2h, writer + local sink 2h, wiring into `response_graph` / `quality_graph` 2h]**

---

## 2.7 Additions

### 2.7a The interrupt budget — reframe the objective [FREEZE 1h]
Precision and recall on planted labels is not what a school buys. The real objective is constrained: **maximize detected-need recall subject to ≤ N interrupts per family per month.** Publish that constraint as a first-class number and let the calibrator optimize under it. It derives free from L5 data and it is the number a coordinator will actually ask about in the first meeting.

### 2.7b Red-team archetypes behind an information barrier [FREEZE 3h]
The parameter-search adversary in §2.2.4 is tooling. The *fingerprint* problem is organizational, and the fix is an information barrier: hand a separate agent (or a separate person) only the README and the public API — **no access to `escalation_triggers.py`, no access to the constants** — and task it with designing a cohort where the system either spams or sleeps. Whatever it finds goes in the report next to the designed cohort. This is the only intellectually honest answer to *"the archetypes were designed by the trigger designer"*, and it is three hours of work with outsized credibility return.

### 2.7c Calibration-first, decision-second [ROADMAP doctrine]
State the direction explicitly: agents may choose *actions*; only calibrated deterministic estimators may cross a *threshold*. Every count-based gate in the harness should eventually become `P(bad state) > q`, because probabilities are comparable across students and counts are not. `attempts ≥ 8` is a story about one seed; `P(mastery < 0.4) > 0.9` is a stated risk tolerance a school can negotiate.

### 2.7d Why offline RL and contextual bandits are premature — and what to log anyway
I would resist this even though it is the fashionable answer, and the reasons are quantitative, not aesthetic:

- **Not enough decisions.** At pilot scale — say 30–100 students, ~2 responses/day, 60 days — you have on the order of 4k–12k decision points, and the *per-student* horizon is ~150. With an action space of 7 policy actions, per-student personalization is statistically empty, and pooled learning re-imports the assumption you are trying to test (that children are interchangeable).
- **The obvious reward is hackable.** Optimizing next-response correctness converges on serving trivially easy items. That is the textbook reward-hacking failure mode for adaptive tutoring, and here it would be invisible: metrics would improve while learning stalled. The honest reward is a delayed assessment outcome, which the pilot does not yet produce.
- **Off-policy evaluation needs logged propensities, which needs a stochastic policy** — deliberately serving worse capsules to real children to generate exploration data. A 30-family pilot cannot absorb that ethics cost, and should not try.
- **A learned policy is not inspectable by a parent**, which breaks guarantee 5 of `architecture.md`.

What to do instead: (i) **log propensities anyway** — record the action set the policy considered and any tie-breaks, ~30 minutes of work, so future OPE remains possible; (ii) restrict learning to the *parameters of interpretable rules*, which is exactly block L1; (iii) if bandits ever arrive, put them on **item selection within a competency** (high T, immediate reward, low harm), never on **interrupt decisions** (low T, delayed reward, high harm). A defensible entry threshold: ~10⁵ logged decisions **and** a proxy reward validated at correlation > 0.3 against a delayed assessment.

### 2.7e Promotion circuit breaker [FREEZE 2h]
Every self-learning loop needs something watching for the ground shifting underneath it. Re-score the golden item set and golden labels weekly. If golden metrics move while population metrics stay flat (or the reverse), **freeze all promotions automatically** and raise a human escalation. Reuses the existing `BoundedAttempts` / circuit-breaker vocabulary and costs almost nothing. It is also the mechanism that makes it safe to leave these loops running unattended during a pilot.

---

## 2.8 AWS mapping, consolidated

| Block | DynamoDB | S3 | EventBridge | Bedrock | AgentCore |
|---|---|---|---|---|---|
| L0 constants | `POLICY#core / V#n` + `ACTIVE` | — | — | — | — |
| L1 calibrator | config versions | tapes, sweep grids, reports (Athena) | nightly re-sweep | none (by design) | — |
| L2 mastery duel | active-model pointer, rolling scores | daily prediction partitions | daily scoring | — | Memory stays conversational only |
| L3 items | item stats + status | candidate pool | retire → regenerate | **batch inference** (overnight regeneration) | — |
| L4 prompts | prompt registry + `ACTIVE` | calibration corpus, **Object Lock** on test/golden | weekly tournament | **batch inference** (candidate scoring) | — |
| L5 flywheel | configs, labels, pointers (`gsi1` on student) | **corpus of record**, daily JSONL | Streams → Firehose | — | — |
| L6e breaker | freeze flag | golden re-scores | weekly | — | — |

Note the shape: **the two blocks that touch children's decisions (L1, L2) contain no LLM at all.** That is the philosophy holding under load, and it is the sentence to put in the video.

---

## 2.9 The 40-hour cut

| Rank | Item | Hours | Why this rank |
|---:|---|---:|---|
| 1 | L5 flywheel schema + `NearMissRecord` | 6 | Irreversible. Signal not captured is gone |
| 2 | L0 constant registry + decouple fast-guess `min_samples` | 3 | Blocks everything else; fixes a live coupling bug |
| 3 | L1c seeded cohort generator | 3 | Without it, "multiple seeds" is a placebo |
| 4 | L1a operating-characteristic / boundary sweep | 4 | Kills the "recalibrated away from the threshold" objection |
| 5 | L1b tape + grid + train/test split + bootstrap CI + plateau | 9 | Turns 8/8 into a curve with error bars |
| 6 | L3 psychometrics honesty (corrected item-total, Wilson, two-strikes, typed reasons) | 6 | Fixes a real contamination bug + a 24%-bank-churn artefact |
| 7 | L6a interrupt-budget metric | 1 | The number a school asks for |
| 8 | L6b red-team archetypes behind an information barrier | 3 | The honest answer to the designer-fingerprint sin |
| 9 | L2 shadow-scoring harness (model-agnostic) | 4 | Makes every future modelling claim falsifiable |
| 10 | L6e promotion circuit breaker | 2 | **First thing to cut if you are over** |
| | **Total** | **41** | |

Deliberately **not** in the freeze: the BKT challenger itself (4h, stretch), the Misconception Probe (3h — cut with regret; it is the best innovation headline here and the first thing I would restore if L1b lands early), the automated prompt-mutation loop (~20h), item probation, Bedrock-batch regeneration.

**What not to build under any circumstances before September 3:** a generic experimentation platform; any online/continuous learning during a live pilot with 30 families; per-student prompt personalization. All three are the classic ways a self-learning story turns into an unaudited one.

---

## 2.10 Sins → repairs, for the record

| Sin named in the report | Block that repairs it |
|---|---|
| Thresholds tuned on the same seed later reported as 8/8 | L1b (train/test seed families, hash-committed test set) |
| Archetypes designed by the trigger designer | L1 adversary (§2.2.4) + L6b information barrier |
| Single seed, no CIs, no baselines | L1b (paired bootstrap, plateau interiority), L2 (base-rate baselines) |
| Scripted LLM doubles | L4 (grader confidence ECE against human labels — the measurement that backs guarantee 3) |
| *Unnamed:* abilities recalibrated away from the threshold | L1a operating-characteristic sweep — the boundary becomes the result |
| *Unnamed:* cohort structure is fixed, so seeds are not independent | L1c seeded cohort generator |
| *Unnamed:* part-whole contamination in item discrimination | L3 corrected item-total correlation |
| *Unnamed:* 24% of the item bank retired on n≈8 statistics | L3 Wilson + two-strikes + weekly retirement budget |
| *Unnamed:* `escalation_min_samples` silently drives the fast-guess detector | L0 decoupling |

Files referenced: `/Users/cs/Documents/Quanta/quanta-repaso/src/repaso/core/harness/mastery.py`, `.../escalation_triggers.py`, `.../psychometrics.py`, `.../sm2.py`, `.../clock.py`, `/Users/cs/Documents/Quanta/quanta-repaso/src/repaso/agents/item_optimizer.py`, `.../adaptation_policy.py`, `/Users/cs/Documents/Quanta/quanta-repaso/src/repaso/simulator/cohort.py`, `.../archetypes.py`, `.../student_sim.py`, `.../demo_clock.py`, `/Users/cs/Documents/Quanta/quanta-repaso/src/repaso/core/orchestration/quality_graph.py`, `/Users/cs/Documents/Quanta/quanta-repaso/src/repaso/schemas/review.py`, `.../provenance.py`, `/Users/cs/Documents/Quanta/quanta-repaso/src/repaso/config/settings.py`.

