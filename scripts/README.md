# Reproducible checks and demonstrations

| Script | Current use | Evidence boundary |
| --- | --- | --- |
| `run_judge_demo.py` | Start the isolated browser experience on localhost:8766; code REPASO-DEMO | Authored models, local data and delivery |
| `run_demo_scenario.py` | Run either teacher-note or reduced-load choice across four labeled dates; `--report` exports seven checkpoints | 24 or 23 assertions; no live AI or Telegram |
| `run_demo_clock.py` | `--days 14 --seed 20260901 --data-dir EMPTY_DIR` | September 6 run: 30 students, 420 sessions, 1,037 responses, all nine gates passed; local journaling took 281.4 seconds |
| `check_installed_package.py` | Run from outside the checkout after installing the wheel | Imports, assets, HTTP routes, both complete scenarios |
| `run_answer_evaluation.py` | Validate 60 synthetic cases; explicit `--live` collects bounded predictions; `--predictions` scores independent labels | No model quality score from authored labels; see evaluation/README.md |
| `analyze_pilot.py` | Aggregate an observed CSV; missing values stay missing | No participants currently; see docs/pilot/README.md |
| `run_cost_report.py` | Read a model call ledger and print spend per role, model and call kind, cache savings, latency percentiles and call counts | Reports only what the provider reported; a ledger without usage prints "not reported", and a replayed run is labelled as one |
| `check_repo_hygiene.py` | Scan tracked files and selected patterns | Run additionally against the release archive; not a general secrets certification |
| `preflight_deploy.py` | Read the account before deploying: caller, region, bootstrap qualifier, the four inference profiles, one bounded model call, Docker, the three secrets and every name the stacks claim | Reads only, exits non-zero on a blocker; a clean run says nothing about whether a deployment succeeds |
| `infra_toggle.py` | Pause/resume the named Repaso routing and schedule resources | External mutation: inspect target account/resources first |
| `teardown.py` | Plan or perform removal of this project's deployment; dry run by default, `--apply` needs a typed confirmation | Only names inside the `repaso` prefix carrying its tag; aborts on anything else. Dry run is read-only; `--apply` has never been run |

A run must have its own output directory. The family CLI refuses to replace an existing nonempty directory. Keep private transcripts and observations under `private/` or `.local_data/`, both excluded from release.

The seed sweep, sensitivity, calendar, armor and school-week scripts are research tools. Their August reports and diagrams describe historical versions and simulator assumptions, including false alarms. Do not reuse their accuracy numbers as current model or family results. The current cohort implementation sends one aggregate teacher note through one parent, scopes a section by invitation and normalizes its label. The current default minimum evidence is nine answers. Models remain authored in all ordinary tests; opt-in live conformance lives under `tests/live/`.
