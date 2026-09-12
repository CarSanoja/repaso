from datetime import UTC, date, datetime

import pytest

from repaso.agents.adaptation_policy import PolicySignals, decide, fallback_decision
from repaso.agents.capsule_composer import compose_capsule
from repaso.agents.escalation_composer import compose_struggle
from repaso.agents.grader import grade_open
from repaso.schemas.common import Lang
from repaso.schemas.grading import EvidenceSpan, GradedBy, StudentResponse
from repaso.schemas.session import PracticeSession
from tests.agents.stress_models import STRESSES, stressed
from tests.agents.test_ingest_fallbacks import COMPETENCY, ITEM, NOW

ALIAS = "Sofi"
THRESHOLD = 0.6
SIGNALS = PolicySignals(
    struggle=False, disengaged=False, fast_guessing=False, ema_accuracy=0.62, streak=1, attempts=11
)
RESPONSE = StudentResponse(
    student_id="s1",
    item_id=str(ITEM.id),
    text="Porque si parto la mitad en cinco pedacitos me quedan 5 de 10.",
    latency_seconds=22.0,
    received_at=NOW,
)
SESSION = PracticeSession(
    id="ses-1", student_id="s1", session_date=date(2026, 9, 12), planned_item_ids=[ITEM.id]
)
EVIDENCE = [EvidenceSpan(quote="5 de 10", source_ref=f"response:{ITEM.id}")]


@pytest.mark.parametrize("kind", STRESSES)
async def test_the_capsule_still_carries_a_reminder_and_the_question(kind):
    model = stressed(kind, {})
    capsule, message = await compose_capsule(
        SESSION, [ITEM], COMPETENCY, ALIAS, Lang.ES, model
    )
    assert model.calls == 1
    assert capsule.concept_snippet.strip()
    assert capsule.item_ids == [ITEM.id]
    assert ITEM.stem in message.text


@pytest.mark.parametrize("kind", STRESSES)
async def test_an_ungraded_answer_is_held_for_a_person(kind):
    model = stressed(
        kind, {"correct": True, "rubric_points": 5.0, "confidence": 0.9, "feedback": "bien"}
    )
    result, quarantine = await grade_open(
        ITEM, RESPONSE, Lang.ES, model, THRESHOLD, NOW, "fam-1"
    )
    assert model.calls == 1
    assert result.quarantined is True
    assert result.graded_by is GradedBy.LLM
    assert result.feedback == ""
    assert quarantine is not None


@pytest.mark.parametrize("kind", STRESSES)
async def test_the_policy_keeps_the_deterministic_decision(kind):
    model = stressed(kind, {"action": "raise_difficulty"})
    decision = await decide(SIGNALS, model)
    assert model.calls == 1
    assert decision == fallback_decision(SIGNALS)


@pytest.mark.parametrize("kind", STRESSES)
async def test_the_escalation_reaches_the_parent_without_its_drafted_note(kind):
    model = stressed(kind, {})
    raised_at = datetime(2026, 9, 12, tzinfo=UTC)
    escalation = await compose_struggle(
        "fam-1", "s1", ALIAS, COMPETENCY, EVIDENCE, Lang.ES, model, raised_at
    )
    assert model.calls == 1
    assert escalation.drafted_note is None
    assert escalation.summary.strip()
    assert [option.key for option in escalation.options] == ["teacher_note", "reduce_load"]
