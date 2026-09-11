# Independent evaluation protocol

This package contains 60 synthetic fourth-grade fraction explanations in ten question groups. Thirty answers belong to development groups and thirty to held-out groups; variants of a question stay in the same split. The set covers correct explanations, wrong reasoning with a correct conclusion, clear errors, partial explanations, ambiguity, informal spelling and injection attempts. It is a narrow diagnostic set, not a representative population sample.

`answer_review_set.jsonl` carries proposed author labels and their origin. `teacher_review_blind.jsonl` omits those labels and model predictions. Give only the blind file to a teacher. They complete `teacher_labels.jsonl` with a pseudonymous reviewer ID, `independent: true`, boolean `correct` and `needs_review`, rubric points and a short reason. Unknown labels remain blank. No labels have been independently completed as of September 12, 2026, which is why every reported figure is agreement with the author's own proposals and no quality claim is allowed.

Validate without calls:

```bash
python scripts/run_answer_evaluation.py
```

Collect a bounded batch using a new output file. `REPASO_EVALUATION_ACCOUNT_ID` names the account the batch is allowed to run in; without it the collector refuses to make a call:

```bash
REPASO_EVALUATION_ACCOUNT_ID=<account> python scripts/run_answer_evaluation.py --live --max-calls 15 --output private/reports/evaluation-batch-1.jsonl
```

The collector asserts that account, omits gold labels from prompts, preserves provider errors and stops at the first error. Use a distinct dataset slice/output for each later batch; never replace failed evidence with a successful retry. Store model ID, prompt version, candidate commit and collection timestamp with the batch. A screened injection has a rule outcome, not a model judgment.

To score completed batches:

```bash
python scripts/run_answer_evaluation.py --predictions private/reports/evaluation-combined.jsonl --labels private/reports/teacher-labels.jsonl
```

The scorer ignores author labels, unfinished reviews, duplicate predictions and IDs outside the dataset. It reports sample sizes, grade agreement, human-review agreement, automatic coverage, false automatic-correct decisions with a Wilson interval, per-category results and confidence bands. Analyze development groups first. Any confidence-threshold or prompt change must be chosen there and frozen before opening held-out results. Report held-out results separately and include all provider/schema failures in coverage denominators.

A threshold of 0.85 is currently a product rule, not a calibrated probability.

## Frozen threshold

On September 12, 2026 the confidence threshold was swept from 0.70 to 1.00 on the thirty
development cases and **frozen at 0.85** for prompt `v1` and `us.anthropic.claude-sonnet-4-6`,
before any held-out case was collected. The criterion was to move it only for a measured
reduction in false automatic-correct decisions; that error was zero at every threshold, so no
candidate was measurably better, and every candidate above 0.85 only shrank the denominator.
The sweep, its denominators and the six disagreements are in
[the development run](../docs/evidence/answer-evaluation-development-2026-09-12.md). Nothing
else was tuned afterwards. Sweep again when the prompt version or the model id changes. A teacher should also review generated questions, keys and rubrics before a family pilot. Publish examples of errors, denominators and limitations; zero observed mistakes in a small sample is not zero risk.

## Probe ablation

The options-only probe now supplies an advisory signal. Its correct guess does not discard a valid item. To test whether it adds value, freeze 30 generated MCQs from material with rights to use, including valid ordinary math questions and deliberately defective keys/distractors. Shuffle option order with seeds 1, 2 and 3. A teacher independently labels validity and option clues before seeing any model output.

Run three arms on the same items/model snapshot: critic only; historical full-question forced-choice probe with its old veto; and critic plus options-only advisory probe. Preserve each critic verdict and probe response. Measure valid-item retention, defective-item rejection, finalized key correctness, extra calls, tokens and wall time. Divide by teacher-labeled valid/defective counts, not all items. Do not treat model solvability as a defect. If advice does not improve teacher-reviewed quality, disable the probe to save cost.

### What was run, September 12, 2026

The ablation ran with one substitution and two additions to the protocol above, each recorded because it limits what the result can say.

The teacher step did not happen: no teacher is available, so validity and option clues are labelled by construction from the defects the harness planted. `ablation_observations.csv` therefore carries `label_source=construction`, `independent_reviewer=none`, and the label columns are named `construction_valid` and `construction_option_clue` instead of the template's `teacher_*` names, so the two can never be confused. Retention and rejection are about planted defects; the teacher-labelled version of this result is still owed. One critic call per item and permutation is shared by the three arms, which isolates the probe and means the arms are not three independent runs; a second critic pass over the first permutation measures how much the critic moves on its own (29 of 30 decisions unchanged).

`ablation_items.json` freezes the thirty items with what was generated and what was planted; `ablation_transcript.jsonl` keeps every critic verdict and probe reply; `ablation_observations.csv` holds 270 rows, one per item, permutation and arm. Rebuild the capture and the report from the transcript with `python scripts/run_probe_ablation.py --analyze`.

The result and its limits are in [`docs/evidence/probe-ablation-2026-09-12.md`](../docs/evidence/probe-ablation-2026-09-12.md). In short: the advisory probe changed none of the 90 decisions, and answered UNKNOWN on 23 of the 24 decisions that carried a planted option clue, so the recommendation is to disable it in the ingest path and keep it for evaluation. The historical veto reached 36/36 planted rejection, but it got there by dropping 13 of the 20 unplanted decisions the critic had kept, leaving 7 of 54; it should not come back.
