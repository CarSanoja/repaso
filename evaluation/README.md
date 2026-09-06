# Independent evaluation protocol

This package contains 60 synthetic fourth-grade fraction explanations in ten question groups. Thirty answers belong to development groups and thirty to held-out groups; variants of a question stay in the same split. The set covers correct explanations, wrong reasoning with a correct conclusion, clear errors, partial explanations, ambiguity, informal spelling and injection attempts. It is a narrow diagnostic set, not a representative population sample.

`answer_review_set.jsonl` carries proposed author labels and their origin. `teacher_review_blind.jsonl` omits those labels and model predictions. Give only the blind file to a teacher. They complete `teacher_labels.jsonl` with a pseudonymous reviewer ID, `independent: true`, boolean `correct` and `needs_review`, rubric points and a short reason. Unknown labels remain blank. No labels have been independently completed as of September 6.

Validate without calls:

```bash
python scripts/run_answer_evaluation.py
```

After authorized Bedrock access is usable, collect a bounded batch using a new output file:

```bash
python scripts/run_answer_evaluation.py --live --max-calls 15 --output private/reports/evaluation-batch-1.jsonl
```

The collector asserts the authorized Quanta account, omits gold labels from prompts, preserves provider errors and stops at the first error. Use a distinct dataset slice/output for each later batch; never replace failed evidence with a successful retry. Store model ID, prompt version, candidate commit and collection timestamp with the batch. A screened injection has a rule outcome, not a model judgment.

To score completed batches:

```bash
python scripts/run_answer_evaluation.py --predictions private/reports/evaluation-combined.jsonl --labels private/reports/teacher-labels.jsonl
```

The scorer ignores author labels, unfinished reviews, duplicate predictions and IDs outside the dataset. It reports sample sizes, grade agreement, human-review agreement, automatic coverage, false automatic-correct decisions with a Wilson interval, per-category results and confidence bands. Analyze development groups first. Any confidence-threshold or prompt change must be chosen there and frozen before opening held-out results. Report held-out results separately and include all provider/schema failures in coverage denominators.

A threshold of 0.85 is currently a product rule, not a calibrated probability. A teacher should also review generated questions, keys and rubrics before a family pilot. Publish examples of errors, denominators and limitations; zero observed mistakes in a small sample is not zero risk.

## Probe ablation

The options-only probe now supplies an advisory signal. Its correct guess does not discard a valid item. To test whether it adds value, freeze 30 generated MCQs from material with rights to use, including valid ordinary math questions and deliberately defective keys/distractors. Shuffle option order with seeds 1, 2 and 3. A teacher independently labels validity and option clues before seeing any model output.

Run three arms on the same items/model snapshot: critic only; historical full-question forced-choice probe with its old veto; and critic plus options-only advisory probe. Preserve each critic verdict and probe response. Measure valid-item retention, defective-item rejection, finalized key correctness, extra calls, tokens and wall time. Divide by teacher-labeled valid/defective counts, not all items. Do not treat model solvability as a defect. `ablation_observations.csv` is the empty capture template; no quality advantage is asserted until completed. If advice does not improve teacher-reviewed quality, disable the probe to save cost.
