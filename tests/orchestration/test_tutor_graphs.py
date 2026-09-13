from datetime import UTC, datetime

from repaso.config.models import ModelRole
from repaso.core.orchestration.context import TutorRun
from repaso.core.orchestration.response_graph import build_response_graph
from repaso.core.orchestration.tutor_graph import build_session_graph
from repaso.schemas.escalation import EscalationKind
from repaso.schemas.grading import StudentResponse
from repaso.schemas.item import Item, ItemKind, ItemStatus
from repaso.schemas.mastery import MasteryLevel, MasteryState
from repaso.schemas.provenance import Provenance, Source
from repaso.schemas.session import Capsule, PracticeSession, SessionStatus
from tests.orchestration.fixtures import FRACTIONS, make_services, seed_family

START = datetime(2026, 9, 1, 19, 0, tzinfo=UTC)


def seed_item(store, item_id: str, kind: ItemKind = ItemKind.MCQ) -> Item:
    item = Item(
        id=item_id,
        competency_id=FRACTIONS,
        kind=kind,
        difficulty=2,
        stem="Which fraction equals 2/4?",
        options=["1/2", "2/8", "3/4"] if kind is ItemKind.MCQ else [],
        answer_key="1/2",
        rationale="both halves",
        rubric="2 points for equivalence reasoning" if kind is ItemKind.OPEN else None,
        status=ItemStatus.ACTIVE,
        provenance=Provenance(source=Source.GENERATED, created_at=START),
    )
    store.put_item(item)
    return item


def seed_session(
    services, student_id: str, item_ids: list[str], session_id: str = "sess1"
) -> PracticeSession:
    session = PracticeSession(
        id=session_id,
        student_id=student_id,
        session_date=services.clock.today(),
        capsule=Capsule(concept_snippet="snippet", item_ids=item_ids),
        status=SessionStatus.DELIVERED,
    )
    services.store.put_session(session)
    return session


def make_response(student_id: str, item_id: str, text: str, latency: float = 20.0):
    return StudentResponse(
        student_id=student_id,
        item_id=item_id,
        text=text,
        latency_seconds=latency,
        received_at=START,
    )


async def test_session_graph_prepares_capsule_before_transport_ack(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_item(services.store, "i2")
    services.models[ModelRole.GENERATE].enqueue({"text": "Las fracciones equivalentes..."})

    run = TutorRun(family=family, student=student)
    await build_session_graph(services, run).invoke_async("session")

    assert run.terminal is None
    assert run.session.status is SessionStatus.PLANNED
    assert run.session.delivery_message is not None
    assert run.session.delivered_at is None
    assert run.session.capsule is not None
    message = run.outbound[0]
    assert message.chat_ref == family.chat_ref
    assert "Leo" in message.text
    assert message.buttons


async def test_second_plan_same_day_is_idempotent(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_session(services, student.id, ["i1"])

    run = TutorRun(family=family, student=student)
    await build_session_graph(services, run).invoke_async("session")

    assert run.terminal == "already_planned"
    assert run.outbound == []


async def test_mcq_correct_updates_mastery_and_moves_to_next_item(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    item = seed_item(services.store, "i1")
    seed_item(services.store, "i2")
    session = seed_session(services, student.id, ["i1", "i2"])
    services.models[ModelRole.STRUCTURED].enqueue({"action": "continue", "reason": "ok"})

    run = TutorRun(
        family=family,
        student=student,
        session=session,
        items=[item],
        response=make_response(student.id, "i1", "1/2"),
    )
    await build_response_graph(services, run).invoke_async("response")

    mastery = services.store.get_mastery(student.id, FRACTIONS)
    assert mastery.attempts == 1 and mastery.streak == 1
    assert services.store.list_spaced(student.id)
    assert services.grade_log.by_student(student.id)
    assert "Correcto" in run.outbound[0].text
    assert run.session.status is SessionStatus.IN_PROGRESS
    assert run.escalations == []


async def test_last_item_completes_the_session_with_streak(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    item = seed_item(services.store, "i1")
    session = seed_session(services, student.id, ["i1"])
    services.models[ModelRole.STRUCTURED].enqueue({"action": "continue", "reason": "ok"})

    run = TutorRun(
        family=family,
        student=student,
        session=session,
        items=[item],
        response=make_response(student.id, "i1", "1/2"),
    )
    await build_response_graph(services, run).invoke_async("response")

    assert run.session.status is SessionStatus.COMPLETED
    assert "racha" in run.outbound[-1].text.lower() or "1" in run.outbound[-1].text


async def test_a_day_that_ends_wrong_closes_without_reciting_a_zero(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    item = seed_item(services.store, "i1")
    session = seed_session(services, student.id, ["i1"])
    services.models[ModelRole.STRUCTURED].enqueue({"action": "continue", "reason": "ok"})

    run = TutorRun(
        family=family,
        student=student,
        session=session,
        items=[item],
        response=make_response(student.id, "i1", "3/4"),
    )
    await build_response_graph(services, run).invoke_async("response")

    closing = run.outbound[-1].text
    assert run.session.status is SessionStatus.COMPLETED
    assert services.store.get_mastery(student.id, FRACTIONS).streak < 1
    assert "0" not in closing
    assert "repasar" in closing


async def test_open_low_confidence_quarantines_and_never_guesses(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    item = seed_item(services.store, "i1", kind=ItemKind.OPEN)
    session = seed_session(services, student.id, ["i1"])
    services.models[ModelRole.JUDGE].enqueue(
        {"correct": True, "rubric_points": 1.5, "confidence": 0.3, "feedback": "casi"}
    )

    run = TutorRun(
        family=family,
        student=student,
        session=session,
        items=[item],
        response=make_response(student.id, "i1", "porque los dos son la mitad"),
    )
    await build_response_graph(services, run).invoke_async("response")

    assert run.grade.correct is None
    assert run.grade.quarantined is True
    assert services.store.list_pending_quarantine(family.id)
    prompt = run.outbound[0]
    assert len(prompt.buttons) == 3
    assert services.store.get_mastery(student.id, FRACTIONS) is None


async def test_struggle_hard_rule_escalates_even_when_model_says_continue(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    item = seed_item(services.store, "i1")
    session = seed_session(services, student.id, ["i1"])
    services.store.put_mastery(
        MasteryState(
            student_id=student.id,
            competency_id=FRACTIONS,
            ema_accuracy=0.2,
            attempts=9,
            correct=1,
            streak=-4,
            level=MasteryLevel.STRUGGLING,
        )
    )
    services.models[ModelRole.STRUCTURED].enqueue({"action": "continue", "reason": "looks fine"})
    services.models[ModelRole.GENERATE].enqueue({"text": "Estimada maestra, un estudiante..."})

    run = TutorRun(
        family=family,
        student=student,
        session=session,
        items=[item],
        response=make_response(student.id, "i1", "2/8"),
    )
    await build_response_graph(services, run).invoke_async("response")

    assert run.decision_action == "escalate_struggle"
    assert run.escalations and run.escalations[0].kind is EscalationKind.STRUGGLE_TRIAGE
    assert len(run.escalations[0].options) == 2
    assert any(m.buttons and m.buttons[0].callback_data.startswith("esc:") for m in run.outbound)
    note_calls = services.models[ModelRole.GENERATE].calls
    assert note_calls and all("Leo" not in str(call) for call in note_calls)


async def test_a_wrong_choice_is_told_why_with_the_reason_already_written(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    item = seed_item(services.store, "i1")
    seed_item(services.store, "i2")
    session = seed_session(services, student.id, ["i1", "i2"])
    services.models[ModelRole.STRUCTURED].enqueue({"action": "continue", "reason": "ok"})

    run = TutorRun(
        family=family,
        student=student,
        session=session,
        items=[item],
        response=make_response(student.id, "i1", "3/4"),
    )
    await build_response_graph(services, run).invoke_async("response")

    assert run.outbound[0].text == f"Todav\u00eda no. {item.rationale}"
    assert services.models[ModelRole.JUDGE].calls == []


async def test_an_open_answer_keeps_the_feedback_the_judge_wrote(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    item = seed_item(services.store, "i1", kind=ItemKind.OPEN)
    session = seed_session(services, student.id, ["i1"])
    services.models[ModelRole.JUDGE].enqueue(
        {"correct": False, "rubric_points": 0.0, "confidence": 0.95, "feedback": "Casi: revisa."}
    )
    services.models[ModelRole.STRUCTURED].enqueue({"action": "continue", "reason": "ok"})

    run = TutorRun(
        family=family,
        student=student,
        session=session,
        items=[item],
        response=make_response(student.id, "i1", "porque s\u00ed"),
    )
    await build_response_graph(services, run).invoke_async("response")

    assert run.outbound[0].text == "Todav\u00eda no. Casi: revisa."
