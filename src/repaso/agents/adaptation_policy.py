from repaso.agents.base import StructuredCallFailed, structured
from repaso.agents.prompts.adaptation_policy import PROMPT_VERSION, SYSTEM
from repaso.core.harness.escalation_triggers import (
    DEFAULT_MIN_ACTIVE_DAYS,
    DEFAULT_SILENT_DAYS,
    engagement_trigger,
    fast_guess_flag,
    struggle_trigger,
)
from repaso.schemas.common import FrozenStrictModel, StrictBaseModel
from repaso.schemas.mastery import MasteryState

ACTIONS = (
    "continue",
    "raise_difficulty",
    "lower_difficulty",
    "switch_to_open",
    "reduce_load",
    "escalate_struggle",
    "escalate_engagement",
)

RAISE_ACCURACY = 0.85
RAISE_STREAK = 3
LOWER_ACCURACY = 0.4


class PolicySignals(FrozenStrictModel):
    struggle: bool
    disengaged: bool
    fast_guessing: bool
    ema_accuracy: float
    streak: int
    attempts: int


class PolicyDecision(StrictBaseModel):
    action: str
    reason: str


def build_signals(
    mastery: MasteryState,
    daily_response_counts: list[int],
    latencies: list[float],
    expected_seconds: float,
    min_samples: int,
    last_escalated_days_ago: int | None,
    cooldown_days: int,
) -> PolicySignals:
    return PolicySignals(
        struggle=struggle_trigger(
            mastery,
            min_samples=min_samples,
            last_escalated_days_ago=last_escalated_days_ago,
            cooldown_days=cooldown_days,
        ),
        disengaged=engagement_trigger(
            daily_response_counts,
            min_active_days=DEFAULT_MIN_ACTIVE_DAYS,
            silent_days_threshold=DEFAULT_SILENT_DAYS,
        ),
        fast_guessing=fast_guess_flag(
            latencies,
            expected_seconds=expected_seconds,
            min_samples=min_samples,
        ),
        ema_accuracy=mastery.ema_accuracy,
        streak=mastery.streak,
        attempts=mastery.attempts,
    )


def fallback_decision(signals: PolicySignals) -> PolicyDecision:
    if signals.struggle:
        return PolicyDecision(
            action="escalate_struggle",
            reason="The struggle trigger fired, so the family decides the next step.",
        )
    if signals.disengaged:
        return PolicyDecision(
            action="escalate_engagement",
            reason="The engagement trigger fired after a run of silent days.",
        )
    if signals.fast_guessing:
        return PolicyDecision(
            action="switch_to_open",
            reason="Answers arrive too fast to be read, so open questions replace choices.",
        )
    if signals.ema_accuracy >= RAISE_ACCURACY and signals.streak >= RAISE_STREAK:
        return PolicyDecision(
            action="raise_difficulty",
            reason="High rolling accuracy and a live streak leave room for harder items.",
        )
    if signals.ema_accuracy < LOWER_ACCURACY:
        return PolicyDecision(
            action="lower_difficulty",
            reason="Rolling accuracy is low, so easier items rebuild footing.",
        )
    return PolicyDecision(
        action="continue",
        reason="No signal asks for a change, so practice continues as planned.",
    )


def signals_prompt(signals: PolicySignals) -> str:
    return (
        "Signals measured for one student:\n"
        f"- struggle trigger fired: {signals.struggle}\n"
        f"- disengagement trigger fired: {signals.disengaged}\n"
        f"- fast guessing detected: {signals.fast_guessing}\n"
        f"- rolling accuracy: {signals.ema_accuracy:.2f}\n"
        f"- current correct streak: {signals.streak}\n"
        f"- attempts recorded: {signals.attempts}\n"
        f"Allowed actions: {', '.join(ACTIONS)}"
    )


async def decide(signals: PolicySignals, model) -> PolicyDecision:
    decision = fallback_decision(signals)
    try:
        reply = await structured(
            model, PolicyDecision, SYSTEM, signals_prompt(signals), PROMPT_VERSION
        )
    except StructuredCallFailed:
        return decision
    if signals.struggle or signals.disengaged:
        return decision
    if signals.fast_guessing and reply.action == "continue":
        return decision
    return reply if reply.action in ACTIONS else decision
