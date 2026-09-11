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

At the default five samples that is 55 calls and an estimate of $0.53. Real
spend comes in well under the estimate, because the allowance assumes far longer
prompts and answers than these probes produce; the report tells you the measured
figure. Raising the sample count raises the estimate proportionally: 18 samples
still fits under the default ceiling and 19 does not.

The prices behind all of this live in `src/repaso/config/pricing.py`, four
rates per model id the fleet can reach: input, output, prompt-cache read and
prompt-cache write. Reasoning tokens are charged at the output rate.

They were last checked on 2026-09-12, for `us-east-1` standard on-demand
inference:

| Model | input | output | cache read | cache write |
| --- | --- | --- | --- | --- |
| Claude Sonnet 4.6 | $3.00 | $15.00 | $0.30 | $3.75 |
| Claude Haiku 4.5 | $1.00 | $5.00 | $0.10 | $1.25 |
| Amazon Nova Lite | $0.06 | $0.24 | $0.015 | $0.00 |
| Amazon Nova Micro | $0.035 | $0.14 | $0.00875 | $0.00 |

Dollars per million tokens, as the source states them; the table in the code
is per thousand. The Nova rates come from the AWS Price List API for Amazon
Bedrock in `us-east-1`, `On-demand Inference`, token types `Input tokens`,
`Output tokens`, `Prompt cache read input tokens` and `Prompt cache write
input tokens`. The Anthropic rates come from the price map the Amazon Bedrock
pricing page itself renders, `US East (N. Virginia)`, standard tier,
publication date 2026-09-11; that page's Priority tier quotes 10 percent
more and is not what these calls buy. The Price List API export does not yet
carry Claude Sonnet 4.6 or Claude Haiku 4.5.

The cache-write column is the five-minute rate. Both Anthropic models also
publish a higher one-hour rate, and a call that writes a one-hour checkpoint
is under-priced here by the difference. The Converse response says which was
used — a measured cache write reported `cacheDetails: [{"ttl": "5m", ...}]` —
but neither the Converse usage block nor the Strands `Usage` type carries
that field into the usage the harness reads, so the ledger records the
five-minute price and nothing in this repository claims otherwise.

The four token classes are billed apart, not nested. A measured pair of calls
with a 3,723-token cached system prefix reported `inputTokens: 15` with
`cacheWriteInputTokens: 3723` on the cold call and `cacheReadInputTokens:
3723` on the warm one, with `totalTokens: 3742` on both — input, output and
the cache class sum to the total, so the cost report charges each class at
its own rate and adds them.

A test asserts that every model the fleet is configured to use has a price and
that no unused model is priced, so adding a model to the fleet fails the
offline suite until its rate is recorded — but the numbers themselves are a
snapshot, and re-checking them is part of turning this tier on after a long
gap.

## What it writes

At the end of the session the run writes
`.local_data/live/conformance-<UTC timestamp>.json` and prints a compact table.
That directory is untracked; nothing from a live run enters the repository.

The JSON holds one row per call — role, schema, model id, outcome, latency in
milliseconds, input and output tokens, and estimated dollars — plus p50 and p95
latency per role, per-schema totals, and the totals for the whole run. Rows are
the raw material; everything else in the file is derived from them, so a later
question the table does not answer can be answered from the rows. A call the
schema rejected still reports the tokens it burned: the model was paid for the
answer whether or not the answer parsed, and a conformance table that zeroes a
failed call under-reports the run.

Beside it the run writes `.local_data/live/model-calls-<UTC timestamp>.jsonl`,
the same ledger the deployed fleet writes, one line per model call. The
conformance report answers whether each schema was filled; the ledger answers
what the run cost, with the usage split by direction and cache class, the stop
reason, the model id and whether the call was live or replayed. After the table
the run prints the cost report over that ledger — spend per role, per model and
per call kind, cache savings, the reasoning share, latency percentiles and the
outcome counts — and `scripts/run_cost_report.py --ledger <path>` prints the
same report for any ledger later.

## Reading the table

This is a real run, three samples per schema, on 2026-09-12:

```
schema conformance at 3 samples per schema
role       schema             calls   ok       in     out       usd
classify   IntakeDecision         3    3     2763      60    0.0002
generate   GeneratedBatch         3    3     4581    3480    0.0659
generate   Snippet                3    3     2550     434    0.0142
generate   TeacherNote            3    3     2550     450    0.0144
judge      CriticFinding          3    3     4554     667    0.0237
judge      OpenGrade              3    3     3447     463    0.0173
probe      ProbeAnswer            3    3     1551      45    0.0001
structured MappingDecision        3    3     3819     165    0.0046
structured PolicyDecision         3    3     2682     282    0.0041
total                            27   27    28497    6046    0.1444

role        calls    p50 ms    p95 ms
classify        3     627.7     881.4
generate        9    3083.6   13807.8
judge           6    2781.5    7086.5
probe           3     493.4     837.9
structured      6    1228.4    1430.8

parsed 27/27, estimated spend $0.1444
```

The run is kept in the repository as
[docs/evidence/live-conformance-2026-09-12.json](../../docs/evidence/live-conformance-2026-09-12.json).

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
than from the estimate. `structured_output` reports that metadata one level
deeper than `stream` does, wrapped in an `event` key, because it runs the same
stream through the SDK's `process_stream`; one reader,
`src/repaso/tools/model_usage.py`, handles both and every other module asks it.

## Extended thinking

Claude Sonnet 4.6 and Claude Haiku 4.5 both support reasoning, and a
`stream()` call with `additionalModelRequestFields={"thinking": ...}` returns
the reasoning as `contentBlockDelta` events carrying `reasoningContent`. The
recorder captures that text into the cassette and the replay emits it back, so
a recorded thinking call replays with its reasoning rather than only its
answer. The cryptographic signature that accompanies a reasoning block is not
kept: it exists to return the block to the provider in a later turn, which a
cassette never does.

Two limits are worth stating plainly, because both bound what this repository
can claim about thinking.

The Converse usage block reports no reasoning token count. A measured Sonnet
call that produced a visible reasoning block reported only `inputTokens`,
`outputTokens` and `totalTokens`; the `Usage` type in the installed Strands
version (1.52.0) carries `inputTokens`, `outputTokens`, `totalTokens`,
`cacheReadInputTokens` and `cacheWriteInputTokens` and nothing else, and no
model provider in that version populates a reasoning count. The usage reader
reads a reasoning count if one ever appears and prices it at the output rate;
until one does, the cost report says the reasoning share is not reported
rather than printing zero.

Thinking cannot be combined with `structured_output` through this SDK version.
`BedrockModel.structured_output` forces a tool with `tool_choice={"any": {}}`,
and `_get_additional_request_fields` deliberately strips the `thinking` key
whenever tool use is forced, because Bedrock rejects the combination. A
measured Sonnet call with thinking configured and a schema requested returned
the schema and no reasoning content at all -- silently, with no error. Every
call the agent fleet makes is a `structured_output` call, so no agent in this
repository can think today, whatever the model supports. The models are wrapped in the same telemetry
instrumentation the production graphs use, and the traces land beside the report
in `.local_data/live/telemetry.jsonl`.

## Sweeping wider than the routing

The tier above asks each schema of the one model its role is bound to. Two scripts
ask wider questions and write their own artifacts rather than passing or failing.
`scripts/run_model_matrix.py` drives every schema against every model id the fleet
is configured to reach, so a routing choice can be compared against the alternatives
instead of asserted; `--schemas` narrows it and `--timeout` turns it into a
deliberate deadline miss. `scripts/run_decision_probe.py` goes further than shape:
for the roles whose output is a closed choice it asks a question whose answer the
fixture defines and counts how often each model gives it. Both report a Wilson 95%
interval beside every count, because a cell of eight samples is a cell of eight
samples. What they measured on September 12, 2026 is in
`docs/evidence/model-profile-2026-09-12.md`.

The harness itself — the registry of schemas, the reporter, and the budget
guard — is covered by ordinary offline tests under `tests/tools/`, which run
against playback models on every commit. One of them parses the agent modules
and asserts that the registry covers exactly the schemas they ask a model to
fill, so a new agent cannot be added without either appearing here or failing
the offline suite.
