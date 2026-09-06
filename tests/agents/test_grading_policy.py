from datetime import UTC, datetime

from repaso.agents.adaptation_policy import (
    PolicyDecision,
    PolicySignals,
    build_signals,
    decide,
    fallback_decision,
)
from repaso.agents.grader import grade_mcq, grade_open
from repaso.schemas.common import Lang
from repaso.schemas.grading import GradedBy, StudentResponse
from repaso.schemas.item import Item, ItemKind
from repaso.schemas.mastery import MasteryLevel, MasteryState
from repaso.schemas.provenance import Provenance, Source
from repaso.schemas.review import QuarantineKind, QuarantineStatus
from repaso.tools.llm import LocalPlaybackModel

GRADED_AT = datetime(2026, 9, 14, 19, 30, tzinfo=UTC)
MIN_SAMPLES = 5
EXPECTED_SECONDS = 40.0
RUSHED = [1.0, 2.0, 1.5, 90.0, 2.0]
THOUGHTFUL = [31.0, 28.0, 44.0, 39.0, 35.0]


class BrokenModel:
    def structured_output(self, output_model, prompt, system_prompt=None):
        async def failing():
            raise RuntimeError("bedrock said no")
            yield {}

        return failing()


def make_item(**overrides) -> Item:
    defaults = dict(
        id="i1",
        competency_id="c1",
        kind=ItemKind.MCQ,
        difficulty=2,
        answer_key="1/2",
        stem="Cuanto es 2/4 simplificado?",
        options=["1/2", "2/8", "4/2"],
        rationale="dividing both terms by two",
        provenance=Provenance(source=Source.GENERATED, created_at=GRADED_AT),
    )
    return Item(**{**defaults, **overrides})


def make_response(text: str) -> StudentResponse:
    return StudentResponse(
        student_id="s1", item_id="i1", text=text, latency_seconds=12.0, received_at=GRADED_AT
    )


def make_signals(**overrides) -> PolicySignals:
    defaults = dict(
        struggle=False,
        disengaged=False,
        fast_guessing=False,
        ema_accuracy=0.6,
        streak=1,
        attempts=10,
    )
    return PolicySignals(**{**defaults, **overrides})


def make_state(**overrides) -> MasteryState:
    defaults = dict(
        student_id="s1",
        competency_id="c1",
        ema_accuracy=0.2,
        attempts=MIN_SAMPLES,
        correct=1,
        streak=0,
        level=MasteryLevel.STRUGGLING,
    )
    return MasteryState(**{**defaults, **overrides})


async def run_open(model, text: str, rubric: str | None = "2 points for the reason"):
    return await grade_open(
        item=make_item(kind=ItemKind.OPEN, options=[], rubric=rubric),
        response=make_response(text),
        lang=Lang.ES,
        model=model,
        confidence_threshold=0.7,
        graded_at=GRADED_AT,
        family_id="f1",
    )


def test_mcq_accepts_the_answer_text_verbatim():
    result = grade_mcq(make_item(), make_response("  1/2 "), GRADED_AT)
    assert result.correct
    assert result.confidence == 1.0
    assert result.graded_by is GradedBy.DETERMINISTIC
    assert result.quarantined is False
    assert result.rubric_points is None
    assert result.feedback == ""


def test_mcq_accepts_the_one_based_option_number():
    assert grade_mcq(make_item(), make_response("1"), GRADED_AT).correct
    item = make_item(options=["2/8", "1/2", "4/2"])
    assert grade_mcq(item, make_response("2"), GRADED_AT).correct
    assert not grade_mcq(item, make_response("1"), GRADED_AT).correct


def test_mcq_rejects_a_wrong_answer_and_quotes_it_verbatim():
    result = grade_mcq(make_item(), make_response("creo que 2/8"), GRADED_AT)
    assert result.correct is False
    assert result.confidence == 1.0
    assert result.evidence.quote == "creo que 2/8"
    assert result.evidence.source_ref == "response:s1:i1"


async def test_open_answer_graded_above_threshold_passes_through():
    model = LocalPlaybackModel(
        [{"correct": True, "rubric_points": 2.0, "confidence": 0.92, "feedback": "Muy bien."}]
    )
    result, quarantine = await run_open(model, "divido arriba y abajo entre dos")
    assert quarantine is None
    assert result.correct is True
    assert result.rubric_points == 2.0
    assert result.graded_by is GradedBy.LLM
    assert result.quarantined is False
    assert result.feedback == "Muy bien."
    assert "es" in model.calls[0]["system_prompt"]
    assert "{lang}" not in model.calls[0]["system_prompt"]


async def test_open_answer_below_threshold_is_quarantined_without_a_verdict():
    model = LocalPlaybackModel(
        [{"correct": True, "rubric_points": 1.0, "confidence": 0.41, "feedback": "Casi."}]
    )
    result, quarantine = await run_open(model, "mitad")
    assert result.correct is None
    assert result.rubric_points is None
    assert result.confidence == 0.41
    assert result.quarantined is True
    assert result.feedback == ""
    assert quarantine is not None
    assert quarantine.kind is QuarantineKind.LOW_CONFIDENCE_GRADE
    assert quarantine.family_id == "f1"
    assert quarantine.status is QuarantineStatus.PENDING
    assert quarantine.payload == {
        "grade_id": None,
        "item_id": "i1",
        "student_id": "s1",
        "answer": "mitad",
        "latency_seconds": 12.0,
    }
    assert quarantine.evidence.quote == "mitad"
    assert quarantine.created_at == GRADED_AT
    assert quarantine.id


async def test_open_answer_quarantines_instead_of_guessing_when_the_model_breaks():
    result, quarantine = await run_open(BrokenModel(), "no se", rubric=None)
    assert result.correct is None
    assert result.confidence == 0.0
    assert result.quarantined is True
    assert quarantine is not None
    assert quarantine.payload["answer"] == "no se"


def signals_from(state: MasteryState, counts: list[int], latencies: list[float]) -> PolicySignals:
    return build_signals(
        mastery=state,
        daily_response_counts=counts,
        latencies=latencies,
        expected_seconds=EXPECTED_SECONDS,
        min_samples=MIN_SAMPLES,
        last_escalated_days_ago=None,
        cooldown_days=7,
    )


def test_build_signals_wires_the_harness_triggers():
    signals = signals_from(make_state(), [3, 2, 0, 0, 0], RUSHED)
    assert (signals.struggle, signals.disengaged, signals.fast_guessing) == (True, True, True)
    assert signals.ema_accuracy == 0.2
    assert signals.attempts == MIN_SAMPLES


def test_build_signals_stays_quiet_for_a_healthy_student():
    healthy = make_state(level=MasteryLevel.SOLID, ema_accuracy=0.9, correct=9, attempts=10)
    signals = signals_from(healthy, [2, 3, 1, 2, 2], THOUGHTFUL)
    assert (signals.struggle, signals.disengaged, signals.fast_guessing) == (False, False, False)


async def test_deterministic_triggers_outrank_the_model_reply():
    struggling = LocalPlaybackModel([{"action": "continue", "reason": "looks fine to me"}])
    silent = LocalPlaybackModel([{"action": "raise_difficulty", "reason": "streak is long"}])
    forced = await decide(make_signals(struggle=True, disengaged=True), struggling)
    engagement = await decide(make_signals(disengaged=True), silent)
    assert forced.action == "escalate_struggle"
    assert engagement.action == "escalate_engagement"


async def test_decide_keeps_a_valid_model_action():
    model = LocalPlaybackModel([{"action": "reduce_load", "reason": "sessions run long"}])
    decision = await decide(make_signals(), model)
    assert decision == PolicyDecision(action="reduce_load", reason="sessions run long")


async def test_decide_falls_back_on_invented_actions_and_broken_calls():
    model = LocalPlaybackModel([{"action": "call_the_principal", "reason": "why not"}])
    invented = await decide(make_signals(ema_accuracy=0.2), model)
    broken = await decide(make_signals(fast_guessing=True), BrokenModel())
    assert invented == fallback_decision(make_signals(ema_accuracy=0.2))
    assert invented.action == "lower_difficulty"
    assert broken.action == "switch_to_open"


def test_fallback_decision_maps_every_signal():
    assert fallback_decision(make_signals(struggle=True)).action == "escalate_struggle"
    assert fallback_decision(make_signals(disengaged=True)).action == "escalate_engagement"
    assert fallback_decision(make_signals(fast_guessing=True)).action == "switch_to_open"
    assert fallback_decision(make_signals(ema_accuracy=0.9, streak=3)).action == "raise_difficulty"
    assert fallback_decision(make_signals(ema_accuracy=0.9, streak=2)).action == "continue"
    assert fallback_decision(make_signals(ema_accuracy=0.39)).action == "lower_difficulty"
    assert fallback_decision(make_signals()).action == "continue"
    assert fallback_decision(make_signals(struggle=True, disengaged=True)).reason
