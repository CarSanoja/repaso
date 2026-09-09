# Cost and blast-radius controls

Every control that bounds what this project can spend or reach is listed here, with
where it is enforced, what trips it, where to read it and the test that proves it.
A control described here and not enforced in a code path would be worse than no
control, so the last two columns are the point of the table.

## What bounds model spend

| Control | Enforced in | What it bounds | When it trips | Read it in | Proven by |
| --- | --- | --- | --- | --- | --- |
| Family daily calls | Application | Model calls one family causes in a day (`daily_llm_budget_calls`, 40) | Reserved before each call; refused when the day is spent | `tools/model_limits.py`, `StateStore.reserve_budget` | `tests/reliability/test_limits_and_recovery.py` |
| Fleet daily calls | Application | Model calls everyone causes in a day (`global_daily_llm_budget_calls`, 400) | Same reservation, second counter | `tools/model_limits.py` | `tests/reliability/test_limits_and_recovery.py` |
| Per-message calls | Application | Model calls one inbound event causes (`message_llm_budget_calls`, 24) | Reserved before the daily counter, keyed by the event's correlation id | `tools/model_limits.py`, `tools/call_quota.py` | `tests/tools/test_model_limits.py`, `tests/reliability/test_blast_radius.py` |
| Items judged per material | Application | Two model calls per item, so twice the number asked for | The generator returns more than `count * MAX_OVERPRODUCTION` | `agents/item_generator.py` | `tests/agents/test_item_generator.py` |
| Model circuit breaker | Application | Repeated calls to a failing model role | Three consecutive failures; recovers after sixty seconds | `core/harness/budgets.py`, `tools/model_limits.py` | `tests/harness/test_budgets.py` |
| Estimated spend by hour | Both | Nothing; it reports | `llm.estimated_usd` summed over an hour exceeds the configured value | `core/telemetry/sink.py`, `infra/stacks/spend_alarms.py` | `tests/infra/test_spend_controls.py` |
| Estimated spend by day | Both | Nothing; it reports | Same metric summed over a day | `infra/stacks/spend_alarms.py` | `tests/infra/test_spend_controls.py` |
| Monthly budgets | Infrastructure | Nothing; they report | Actual spend on this project's tagged resources crosses 50%, 80% or 100%, or a forecast crosses 100% | `infra/stacks/budget_alerts.py` | `tests/infra/test_spend_controls.py` |

The per-message ceiling does not apply to the daily close, whose cost is proportional
to the number of families enrolled rather than to anything anyone sends. The fleet
daily ceiling is what bounds that.

## What bounds reach from the public internet

| Control | Enforced in | What it bounds | When it trips | Read it in | Proven by |
| --- | --- | --- | --- | --- | --- |
| Webhook secret | Application | Anyone without the shared header | Missing or wrong `X-Telegram-Bot-Api-Secret-Token` | `api/webhook.py` | `tests/api/test_api.py` |
| Chat rate limit | Application | Messages one chat causes per minute (`chat_messages_per_minute`, 12) | Reserved before anything is published | `channel/throttle.py` | `tests/channel/test_throttle.py`, `tests/api/test_webhook_throttle.py` |
| Unknown chat allowance | Application | Messages per day from a chat with no family and no enrollment in progress (`unknown_chat_daily_messages`, 8) | Reserved before anything is published | `channel/throttle.py` | `tests/channel/test_throttle.py`, `tests/api/test_webhook_throttle.py` |
| HTTP API rate and burst | Infrastructure | Requests per second the public route accepts | Above the configured rate or burst | `infra/stacks/api_stack.py` | `tests/infra/test_spend_controls.py` |
| Reserved concurrency | Infrastructure | Simultaneous webhook, worker and scheduler executions | Above the reservation; further invocations are throttled | `infra/stacks/api_stack.py` | `tests/infra/test_spend_controls.py` |
| Queue concurrency | Infrastructure | Workers one queue can open | Above `worker_queue_concurrency` | `infra/stacks/api_stack.py` | `tests/infra/test_spend_controls.py` |
| Intake screening | Both | What reaches a model, and what reaches a family | Harmful content, prompt attacks and identifiers | `tools/guardrails.py`, `infra/stacks/guardrails_stack.py` | `tests/tools/test_guardrails.py`, `tests/infra/test_synth.py` |

A refused message still answers HTTP 200, because the channel redelivers anything
else and the purpose is to stop paying for the chat, not to argue with it.

## What bounds a message that will not succeed

| Control | Enforced in | What it bounds | Read it in | Proven by |
| --- | --- | --- | --- | --- |
| Dead letter queue | Infrastructure | Three receives, then the message leaves the work queue | `infra/stacks/messaging_stack.py` | `tests/infra/test_spend_controls.py` |
| Visibility over timeout | Infrastructure | Redelivery while the worker still holds the message | `infra/stacks/messaging_stack.py`, `infra/stacks/api_stack.py` | `tests/infra/test_spend_controls.py` |
| Spent ceiling is terminal | Application | Redelivering work that a ceiling will refuse again | `runtime/ceilings.py`, `lambdas/worker.py` | `tests/lambdas/test_worker_lambda.py` |
| Replay costs nothing new | Application | A redelivered event re-spending the model | `runtime/entrypoint.py`, `tools/model_limits.py` | `tests/tools/test_model_limits.py` |
| Queue stall alarm | Infrastructure | Nothing; it reports | `infra/stacks/observability_stack.py` | `tests/infra/test_spend_controls.py` |
| Dead letter depth alarm | Infrastructure | Nothing; it reports | `infra/stacks/observability_stack.py` | `tests/infra/test_synth.py` |

A redelivered event carries the same idempotency key, so its per-message allowance is
the one the first delivery already spent. Three receives of an expensive message cost
one message's worth of model calls, not three.

## What happens when a spend ceiling trips

1. The call is refused before it is made. Nothing is sent to a model.
2. The family is told, in the language they chose, that practice is paused for the
   rest of today and that nothing they sent was lost (`practice_paused_today`).
3. The notice is delivered through the outbox under one key per reason per day, so a
   family that sends six more things is told once.
4. `spend.daily_ceiling.tripped` or `spend.message_ceiling.tripped` is published, and
   an alarm on that metric publishes to the alerts topic.
5. The invocation answers `spend_ceiling_reached`. The worker accepts the message
   rather than redelivering it, so nothing loops and nothing reaches the dead letter
   queue for a reason that is not a fault.

A provider outage and an open circuit breaker keep the older behaviour: the family is
told the service is briefly unavailable and the work is preserved, and the message is
redelivered, because for those the work really does resume.

## What these controls do not do

- Budgets alert. They do not stop spending, and neither do the spend alarms.
- Budgets read zero until the cost allocation tag named in `infra/config.py` is
  activated in billing. Synthesis says so; until it is done, the filtered budgets are
  accurate about nothing.
- `llm.estimated_usd` counts only calls where the provider reported token usage and
  the model appears in the dated table in `config/pricing.py`. It is an estimate of
  model spend and excludes everything else the deployment costs.
- The application cannot tell a spent family ceiling from a spent fleet ceiling: both
  come back as one refusal. Many distinct families refused in the same window is what
  distinguishes them, which is why the alarm fires on any trip.
- The circuit breaker lives in one process and starts closed in a new one.
- The file-backed allowance store used outside the deployment keeps rows forever; the
  deployed table expires them through its time-to-live attribute.
- Reserved concurrency takes its reservation from the shared concurrency pool. It
  bounds this project and, by the same token, stops this project from consuming what
  else is deployed alongside it.
- In durable mode retained databases and buckets survive stack removal; in ephemeral
  mode they are deleted with everything in them. [The deployment guide](../../deploy/README.md)
  is where that choice is made.

## Decisions that are not in the code

These have defaults chosen to be safe rather than right, and the values belong to
whoever runs the pilot. All of them are CDK context or settings.

| Decision | Where | Default |
| --- | --- | --- |
| Address that receives every budget and alarm | `alert_email` context | none, and synthesis warns |
| Activation of the cost allocation tag | Billing console | not activated |
| Monthly budget amounts and thresholds | `budget_limits`, `budget_thresholds` | 25 and 40 USD at 50/80/100% |
| Estimated model spend that should raise an alarm | `hourly_model_spend_usd`, `daily_model_spend_usd` | 2 and 10 USD |
| Calls a family, the fleet and one message may cause | `REPASO_DAILY_LLM_BUDGET_CALLS`, `REPASO_GLOBAL_DAILY_LLM_BUDGET_CALLS`, `REPASO_MESSAGE_LLM_BUDGET_CALLS` | 40, 400, 24 |
| Messages a chat and an unknown chat may cause | `REPASO_CHAT_MESSAGES_PER_MINUTE`, `REPASO_UNKNOWN_CHAT_DAILY_MESSAGES` | 12 per minute, 8 per day |
| Refused chats in fifteen minutes worth an alarm | `refused_chats_per_window` | 20 |
| Concurrency ceilings | `webhook_reserved_concurrency`, `worker_reserved_concurrency`, `scheduler_reserved_concurrency`, `worker_queue_concurrency` | 10, 15, 5, 4 |
| Public route rate and burst | `webhook_rate_limit`, `webhook_burst_limit` | 20 and 40 per second |

Nothing here is claimed to be deployed. The infrastructure rows describe synthesized
templates; see [the evidence register](../evidence/README.md) for what has been run.
