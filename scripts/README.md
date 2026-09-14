# Run, inspect and verify Repaso

| Script | Current use | Evidence boundary |
| --- | --- | --- |
| `run_memory_observer.py --rehearsal --port 8870` | School Community Memory dashboard and three-column episode; code REPASO-VIEW | Scripted model replies, temporary local state and delivery; controlled clock; no Telegram or paid inference |
| `run_memory_observer.py --profile YOUR_PROFILE --family-id AUTHORIZED_FAMILY_ID` | Read-only local observer of the AWS deployment on localhost:8767 | Explicit family allowlist; DynamoDB state and correlated CloudWatch events; no Telegram sends or work publication |
| `run_judge_demo.py` | Start the isolated browser experience on localhost:8766; code REPASO-DEMO | Recorded model outputs, local data and delivery |
| `run_demo_scenario.py` | Run either teacher-note or reduced-load choice across four labeled dates; `--report` exports seven checkpoints | 24 or 23 assertions; day one replays the recorded cassette and the days after it are authored; no live AI or Telegram |
| `record_demo_cassette.py` | Record the demonstration journey against Amazon Bedrock into a cassette and its provenance; needs credentials and spends money | One recording, one day: the cassette replays those answers and is not evidence the models would answer so again |
| `run_demo_clock.py` | `--days 14 --seed 20260901 --data-dir EMPTY_DIR` | September 6 run: 30 students, 420 sessions, 1,037 responses, all nine gates passed; local journaling took 281.4 seconds |
| `check_installed_package.py` | Run from outside the checkout after installing the wheel | Imports, assets, HTTP routes, both complete scenarios |
| `run_answer_evaluation.py` | Validate 60 synthetic cases; explicit `--live` collects a bounded slice from `--start`; `--predictions` scores a saved batch at `--threshold`, against teacher or `--label-source author-proposed` labels | No model quality score from authored labels; see evaluation/README.md |
| `report_answer_evaluation.py` | Build the publication-safe artifact for a collected batch: denominators, agreement, threshold sweep, measured spend from the batch ledger and every disagreement verbatim | Agreement with whichever labels it was given; raw batches stay under `private/` |
| `analyze_pilot.py` | Aggregate an observed CSV; missing values stay missing | No participants currently; see docs/pilot/README.md |
| `run_probe_ablation.py` | `--freeze` generates and plants the ablation item set; `--run` puts every item through the critic and both probes; `--analyze` writes the capture rows and the per-arm report | Labels are planted defects, not teacher labels; see the probe ablation section of evaluation/README.md |
| `run_cost_report.py` | Read a model call ledger and print spend per role, model and call kind, cache savings, latency percentiles and call counts | Reports only what the provider reported; a ledger without usage prints "not reported", and a replayed run is labelled as one |
| `run_model_matrix.py` | Drive every schema in the live registry against every model id the fleet is configured to reach, at N samples a cell; `--timeout` measures a deliberate deadline miss | Parse rate, latency and tokens as the provider reported them; never item quality. A cell of eight samples is eight samples, and its Wilson interval says so |
| `run_decision_probe.py` | Ask each model a question whose answer the fixture defines, N times, and count how often it gives it | Covers only the roles whose output is a closed choice; the policy row measures agreement with the deterministic action, not truth |
| `run_live_journey.py` | Run the complete family scenario with live inference and local everything else, then print the cost report over the ledger it wrote | One day, one synthetic family; the scenario's follow-up days use authored playback and are not ledgered. Live generation varies, so the cassette-pinned beat counts will not hold |
| `check_repo_hygiene.py` | Scan tracked files and selected patterns | Run additionally against the release archive; not a general secrets certification |
| `preflight_deploy.py` | Read the account before deploying: caller, region, bootstrap qualifier, the four inference profiles, one bounded model call, Docker, the three secrets and every name the stacks claim | Reads only, exits non-zero on a blocker; a clean run says nothing about whether a deployment succeeds |
| `infra_toggle.py` | Pause/resume the named Repaso routing and schedule resources | External mutation: inspect target account/resources first |
| `teardown.py` | Plan or perform removal of this project's deployment; dry run by default, `--apply` needs a typed confirmation | Only names inside the `repaso` prefix carrying its tag; aborts on anything else. Dry run is read-only; `--apply` has never been run |

## Start the product rehearsal

From the repository root, after installing `.[dev]` with `requirements.lock`:

```bash
python scripts/run_memory_observer.py --rehearsal --port 8870
```

Open **http://127.0.0.1:8870/judge/memory/** with **`REPASO-VIEW`**. Run the four
labeled steps in order, then explore family, learner, topic and recorded-day
views. The rehearsal's temporary state resets when the process stops.

For real AWS observation, supply your own authorized profile and family ID:

```bash
python scripts/run_memory_observer.py --profile YOUR_PROFILE --region us-east-1 --family-id AUTHORIZED_FAMILY_ID --port 8767
```

This binds to loopback and reads the deployment; it is not a public hosted URL.
The initial log lookback defaults to 24 hours and can be changed with
`--history-minutes` (1–10080). Missing log links remain labeled as missing.
See the [episode runbook](../docs/submission/episode-demo-runbook.md) and
[deployment guide](../deploy/README.md) for prerequisites and evidence boundaries.

A run must have its own output directory. The family CLI refuses to replace an existing nonempty directory. Keep private transcripts and observations under `private/` or `.local_data/`, both excluded from release.

The seed sweep, sensitivity, calendar, armor and school-week scripts are research tools. Their August reports and diagrams describe historical versions and simulator assumptions, including false alarms. Do not reuse their accuracy numbers as current model or family results. The current cohort implementation sends one aggregate teacher note through one parent, scopes a section by invitation and normalizes its label. The current default minimum evidence is nine answers. No ordinary test calls a model: they replay a cassette or a playback script, and opt-in live conformance lives under `tests/live/`.
