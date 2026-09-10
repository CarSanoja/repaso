"""Run one item through the shared critic and both probes, keeping every call it made."""

import asyncio
from datetime import datetime
from random import Random

from ablation_arms import ProbeReply, ask_advisory, ask_forced_choice
from ablation_items import FrozenItem, as_item, presented_options

from repaso.agents.item_critic import critique
from repaso.schemas.common import FrozenStrictModel
from repaso.tools.call_cost import cost_or_none
from repaso.tools.call_ledger import CallLedger, CallRecord
from repaso.tools.model_limits import ModelLimitReached

STAGE_CRITIC = "critic"
STAGE_CRITIC_REPEAT = "critic_repeat"
STAGE_FORCED_CHOICE = "probe_forced_choice"
STAGE_ADVISORY = "probe_advisory"

RETRY_ATTEMPTS = 6
RETRY_BASE_SECONDS = 4.0


class CallLog(FrozenStrictModel):
    stage: str
    call_id: str
    role: str
    model_id: str
    prompt_version: str = ""
    outcome: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    usd: float = 0.0
    error: str = ""


class Review(FrozenStrictModel):
    item_id: str
    permutation_seed: int
    options: list[str]
    answer_key: str
    critic_accepted: bool
    critic_flaws: list[str]
    critic_notes: str
    critic_repeat_accepted: bool | None = None
    forced_choice: ProbeReply
    advisory: ProbeReply
    calls: list[CallLog]


class CapturingLedger:
    def __init__(self, inner: CallLedger) -> None:
        self.inner = inner
        self.written: list[CallRecord] = []

    def append(self, record: CallRecord) -> None:
        self.written.append(record)
        self.inner.append(record)

    def records(self) -> list[CallRecord]:
        return list(self.written)


def _log(stage: str, record: CallRecord) -> CallLog:
    usage = record.usage
    cost = record.cost or (cost_or_none(record.model_id, usage) if usage else None)
    return CallLog(
        stage=stage,
        call_id=record.call_id,
        role=record.role,
        model_id=record.model_id,
        prompt_version=record.prompt_version or "",
        outcome=record.outcome.value,
        input_tokens=usage.input_tokens if usage else 0,
        output_tokens=usage.output_tokens if usage else 0,
        latency_ms=record.latency_ms,
        usd=cost.total_usd if cost else 0.0,
        error=record.error,
    )


async def _with_retry(call, sleeper=asyncio.sleep, rng: Random | None = None):
    jitter = rng or Random()
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return await call()
        except ModelLimitReached:
            if attempt == RETRY_ATTEMPTS - 1:
                raise
            await sleeper(RETRY_BASE_SECONDS * 2**attempt * (0.5 + jitter.random()))
    raise RuntimeError("unreachable")


async def _staged(ledger: CapturingLedger, stage: str, call, logs: list[CallLog]):
    before = len(ledger.written)
    result = await _with_retry(call)
    logs.extend(_log(stage, record) for record in ledger.written[before:])
    return result


async def review_item(
    frozen: FrozenItem,
    seed: int,
    source_text: str,
    grade: int,
    judge,
    probe,
    ledger: CapturingLedger,
    now: datetime,
    model_id: str,
    repeat_critic: bool = False,
) -> Review:
    options = presented_options(frozen, seed)
    item = as_item(frozen, options, now, model_id)
    logs: list[CallLog] = []
    verdict = await _staged(
        ledger, STAGE_CRITIC, lambda: critique(item, source_text, grade, judge), logs
    )
    repeat = None
    if repeat_critic:
        again = await _staged(
            ledger, STAGE_CRITIC_REPEAT, lambda: critique(item, source_text, grade, judge), logs
        )
        repeat = again.accepted
    forced = await _staged(
        ledger, STAGE_FORCED_CHOICE, lambda: ask_forced_choice(item, probe), logs
    )
    advisory = await _staged(ledger, STAGE_ADVISORY, lambda: ask_advisory(item, probe), logs)
    return Review(
        item_id=frozen.item_id,
        permutation_seed=seed,
        options=options,
        answer_key=frozen.answer_key,
        critic_accepted=verdict.accepted,
        critic_flaws=[flaw.value for flaw in verdict.flaws],
        critic_notes=verdict.notes,
        critic_repeat_accepted=repeat,
        forced_choice=forced,
        advisory=advisory,
        calls=logs,
    )
