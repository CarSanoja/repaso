# The live tier

Every other test in this repository runs against a playback model. The tests in
this directory are the only ones that call Amazon Bedrock, and they answer two
questions the offline suite cannot: does each model the fleet is configured to
use actually answer, and does it fill the exact schema the agent asks for, every
time.

They are skipped by default. Nothing here runs, and nothing here spends money,
unless you turn it on deliberately.

## Turning it on

```
REPASO_LIVE_TESTS=1 REPASO_AWS_REGION=us-east-1 pytest tests/live
```

Both are required. Without `REPASO_LIVE_TESTS=1` every test in this directory
is skipped; with the flag but no region — `REPASO_AWS_REGION`, or `AWS_REGION`
as a fallback — they are skipped too, and the skip message says which of the
two was missing. Every test here also carries the `live` marker, so
`pytest -m "not live"` excludes the whole tier and `pytest -m live` selects it.

Ordinary AWS credentials for that region must be in the environment. Bedrock
must have on-demand access enabled for the models listed in
`src/repaso/config/models.py`.

Two more variables tune the run:

| Variable | Default | Meaning |
| --- | --- | --- |
| `REPASO_LIVE_SAMPLES` | `5` | how many times each schema is asked for |
| `REPASO_LIVE_BUDGET_USD` | `2.00` | the ceiling the run refuses to exceed |

## What it costs

Before the first call, the run prices itself: the number of schemas times the
sample count times a deliberately generous per-call token allowance, charged at
the on-demand rate for the model each role is bound to, plus one short prompt
for every model in the default and fallback chains. The estimate is printed
whether or not it passes, and a run priced above `REPASO_LIVE_BUDGET_USD` is
refused before a single call is made.

At the default five samples that is 55 calls and an estimate of $0.66. Real
spend comes in well under the estimate, because the allowance assumes far longer
prompts and answers than these probes produce; the report tells you the measured
figure. Raising the sample count raises the estimate proportionally: 15 samples
still fits under the default ceiling and 16 does not.

The prices behind all of this live in `src/repaso/config/pricing.py`, one entry
per model id the fleet can reach. The Amazon Nova Lite and Nova Micro rates were
checked on 2026-09-03 against the AWS Price List bulk export for Amazon Bedrock
in `us-east-1` (publication date 2026-09-01). The Anthropic rates were checked
on 2026-09-12 against the Price List API for `AmazonBedrockFoundationModels` in
`US East (N. Virginia)`, and they are the `USE1_InputTokenCount` and
`USE1_OutputTokenCount` dimensions — the geographic cross-Region rate, which is
what a `us.` inference profile charges. The `_Global` dimensions of the same
products are about ten percent lower and belong to the `global.` profiles the
fleet does not call.

A test asserts that every model the fleet is configured to use has a price, that
no unused model is priced, and that the two Anthropic entries match the
geographic rate per million tokens, so adding a model to the fleet fails the
offline suite until its rate is recorded — but the numbers themselves are a
snapshot, and re-checking them is part of turning this tier on after a long gap.

## What it writes

At the end of the session the run writes
`.local_data/live/conformance-<UTC timestamp>.json` and prints a compact table.
That directory is untracked; nothing from a live run enters the repository.

The JSON holds one row per call — role, schema, model id, outcome, latency in
milliseconds, input and output tokens, and estimated dollars — plus p50 and p95
latency per role, per-schema totals, and the totals for the whole run. Rows are
the raw material; everything else in the file is derived from them, so a later
question the table does not answer can be answered from the rows.

## Reading the table

This is a real run, three samples per schema, on 2026-09-12:

```
schema conformance at 3 samples per schema
role       schema             calls   ok       in     out       usd
classify   IntakeDecision         3    3     2763      60    0.0002
generate   GeneratedBatch         3    3     4581    3531    0.0667
generate   Snippet                3    3     2550     430    0.0141
generate   TeacherNote            3    3     2550     445    0.0143
judge      CriticFinding          3    3     4554     629    0.0231
judge      OpenGrade              3    3     3447     483    0.0176
probe      ProbeAnswer            3    3     1551      45    0.0001
structured MappingDecision        3    3     3819     165    0.0046
structured PolicyDecision         3    3     2682     255    0.0040
total                            27   27    28497    6043    0.1447

role        calls    p50 ms    p95 ms
classify        3     578.9     871.8
generate        9    3138.2   16609.4
judge           6    3894.8    4982.6
probe           3     500.8     773.4
structured      6    1155.3    1364.1

parsed 27/27, estimated spend $0.1447
```

The `ok` column against `calls` is the conformance figure, and the run fails
unless they match on every line: a schema that parsed four times out of five is
a schema the production path will drop one call in five, which is why the bar
is 100 percent rather than a threshold. A failing case names the schema, the
sample number, and the reason — a timeout, a payload the schema rejected, or a
transport error — because those three failures want different fixes.

The latency block is what the roles cost in time. p95 is the number to plan a
timeout against; p50 is the number a family feels.

## How it measures

Each sample is one call, and a call is never retried. A retry would repair
exactly the failure this tier exists to find, so a failed call is recorded with
its outcome and the run moves on. The only bound is a timeout, and a call that
exceeds it is a failed call, not an error thrown out of the harness.

Token counts come from the usage metadata on the Converse stream, so the
dollars in the report are computed from what the call actually consumed rather
than from the estimate. The models are wrapped in the same telemetry
instrumentation the production graphs use, and the traces land beside the report
in `.local_data/live/telemetry.jsonl`.

The harness itself — the registry of schemas, the reporter, and the budget
guard — is covered by ordinary offline tests under `tests/tools/`, which run
against playback models on every commit. One of them parses the agent modules
and asserts that the registry covers exactly the schemas they ask a model to
fill, so a new agent cannot be added without either appearing here or failing
the offline suite.
