import pytest

from repaso.agents.capsule_composer import item_buttons
from repaso.config.models import ModelRole
from repaso.core.orchestration.adaptations import apply_adaptation
from repaso.core.orchestration.channel_runner import handle_channel_message
from repaso.core.orchestration.privacy import forget_family
from repaso.core.orchestration.quarantine_resolution import resolve_quarantine
from repaso.core.orchestration.runner import handle_answer, resolve_escalation, start_daily_session
from repaso.schemas.channel import ChannelKind, InboundMessage
from repaso.schemas.escalation import Escalation, EscalationKind, EscalationOption
from repaso.schemas.grading import GradedBy
from repaso.schemas.item import ItemKind
from repaso.schemas.session import SessionStatus
from tests.orchestration.fixtures import (
    FRACTIONS,
    seed_family,
    seed_held_answer,
    seed_open_item,
)
from tests.orchestration.fixtures import (
    make_services as _make_services,
)


def make_services(settings):
    services = _make_services(settings)
    for _ in range(3):
        services.models[ModelRole.GENERATE].enqueue({"text": "Recuerda sumar las cantidades."})
    for _ in range(8):
        services.models[ModelRole.STRUCTURED].enqueue({"action": "continue", "reason": "fixture"})
    return services


class IntermittentSender:
    def __init__(self, fail_at):
        self.fail_at = fail_at
        self.attempts = 0
        self.sent = []

    def send(self, message):
        self.attempts += 1
        if self.attempts == self.fail_at:
            raise ConnectionError("simulated delivery failure")
        self.sent.append(message)
        return str(len(self.sent))


def seed_mcqs(services, family_id=None, count=3):
    items = []
    for n in range(count):
        item = seed_open_item(services.store, f"item-{n}").model_copy(
            update={
                "family_id": family_id,
                "kind": ItemKind.MCQ,
                "difficulty": n + 1,
                "stem": f"¿Cuánto es {n} + 1?",
                "options": [str(n + 1), "99", "100"],
                "answer_key": str(n + 1),
            }
        )
        services.store.put_item(item)
        items.append(item)
    return items


@pytest.mark.parametrize("action,difficulty", [("raise_difficulty", 3), ("lower_difficulty", 1)])
async def test_difficulty_changes_actual_questions_without_reviving_expired_flags(
    settings, action, difficulty
):
    s = make_services(settings)
    family, student = seed_family(s.store)
    seed_mcqs(s, family.id)
    apply_adaptation(s, family, student.id, FRACTIONS, "switch_to_open", source="old")
    s.clock.advance(days=8)
    apply_adaptation(s, family, student.id, FRACTIONS, action, difficulty=2, source="new")
    run = await start_daily_session(s, family, student)
    selected = [s.store.get_item(identity) for identity in run.session.planned_item_ids]
    assert selected and all(item.difficulty == difficulty for item in selected)
    assert all(item.kind is ItemKind.MCQ for item in selected)


@pytest.mark.asyncio
async def test_session_recovers_after_transport_failure_without_regenerating(settings):
    s = make_services(settings)
    family, student = seed_family(s.store)
    seed_mcqs(s, family.id)
    s.sender = IntermittentSender(1)
    with pytest.raises(ConnectionError):
        await start_daily_session(s, family, student)
    pending = s.store.get_session_by_date(student.id, s.clock.today())
    assert pending.status is SessionStatus.PLANNED and pending.delivered_at is None
    retried = await start_daily_session(s, family, student)
    assert retried.session.id == pending.id
    assert retried.session.status is SessionStatus.DELIVERED
    assert len(s.sender.sent) == 1
    await start_daily_session(s, family, student)
    assert len(s.sender.sent) == 1


@pytest.mark.asyncio
async def test_response_retry_finishes_unsent_messages_without_grading_the_next_question(settings):
    s = make_services(settings)
    family, student = seed_family(s.store)
    seed_mcqs(s, family.id)
    await start_daily_session(s, family, student)
    s.sender = IntermittentSender(2)
    with pytest.raises(ConnectionError):
        await handle_answer(s, family, student, "1", 40, response_id="answer-1")
    assert len(s.grade_log.by_student(student.id)) == 1
    retried = await handle_answer(s, family, student, "1", 40, response_id="answer-1")
    assert len(s.grade_log.by_student(student.id)) == 1
    assert retried.session.current_item_index == 1
    assert len(s.sender.sent) == 2
    assert s.store.get_mastery(student.id, FRACTIONS).attempts == 1


@pytest.mark.parametrize("accepted", [True, False])
def test_human_resolution_survives_a_crash_between_learning_writes(settings, monkeypatch, accepted):
    s = make_services(settings)
    family, student = seed_family(s.store)
    seed_open_item(s.store)
    held = seed_held_answer(s.store, family.id, student.id)
    original = s.store._tables.write
    failed = False

    def flaky(table, rows):
        nonlocal failed
        if table == "spaced" and not failed:
            failed = True
            raise OSError("simulated process failure after mastery write")
        original(table, rows)

    monkeypatch.setattr(s.store._tables, "write", flaky)
    with pytest.raises(OSError):
        resolve_quarantine(s, family, held, accepted)
    resolve_quarantine(s, family, held, not accepted)
    state = s.store.get_mastery(student.id, FRACTIONS)
    assert (state.attempts, state.correct) == (1, int(accepted))
    grades = s.grade_log.by_student(student.id)
    assert len(grades) == 1
    assert grades[0].graded_by is GradedBy.HUMAN and grades[0].correct is accepted


@pytest.mark.asyncio
async def test_callbacks_are_small_and_reject_another_family_or_old_question(settings):
    s = make_services(settings)
    family, student = seed_family(s.store)
    other, _ = seed_family(s.store, "f2", "200")
    items = seed_mcqs(s, family.id)
    session = (await start_daily_session(s, family, student)).session
    button = item_buttons(session.id, items[0])[0]
    assert len(button.callback_data.encode()) <= 64
    inbound = InboundMessage(
        channel=ChannelKind.TELEGRAM,
        chat_ref=other.chat_ref,
        message_ref="alien",
        callback_data=button.callback_data,
        received_at=s.clock.now(),
    )
    await handle_channel_message(s, inbound)
    assert s.grade_log.by_student(student.id) == []
    inbound = inbound.model_copy(update={"chat_ref": family.chat_ref, "message_ref": "first"})
    await handle_channel_message(s, inbound)
    await handle_channel_message(s, inbound.model_copy(update={"message_ref": "stale"}))
    assert len(s.grade_log.by_student(student.id)) == 1


@pytest.mark.asyncio
async def test_adaptation_changes_the_next_day_and_expires(settings):
    s = make_services(settings)
    family, student = seed_family(s.store)
    seed_mcqs(s, family.id)
    apply_adaptation(s, family, student.id, FRACTIONS, "switch_to_open", source="a")
    apply_adaptation(s, family, student.id, FRACTIONS, "reduce_load", source="b")
    run = await start_daily_session(s, family, student)
    assert len(run.items) == 1 and run.items[0].kind is ItemKind.OPEN
    assert run.outbound[0].buttons == []
    s.clock.advance(days=8)
    run = await start_daily_session(s, family, student)
    assert len(run.items) == 3


def test_teacher_note_is_delivered_and_unknown_option_cannot_resolve(settings):
    s = make_services(settings)
    family, student = seed_family(s.store)
    escalation = Escalation(
        id="esc",
        kind=EscalationKind.STRUGGLE_TRIAGE,
        family_id=family.id,
        student_id=student.id,
        competency_id=FRACTIONS,
        summary="Dificultad persistente",
        options=[EscalationOption(key="teacher_note", label="Nota", tradeoff="")],
        drafted_note="Texto listo para compartir con el docente.",
        created_at=s.clock.now(),
    )
    s.store.put_escalation(escalation)
    with pytest.raises(ValueError):
        resolve_escalation(s, family, escalation, "unavailable")
    resolve_escalation(s, family, escalation, "teacher_note")
    assert s.sender.sent[0]["text"] == escalation.drafted_note
    resolve_escalation(s, family, escalation, "teacher_note")
    assert len(s.sender.sent) == 2


@pytest.mark.asyncio
async def test_forget_removes_all_owned_data_and_preserves_other_family(settings):
    s = make_services(settings)
    family, student = seed_family(s.store)
    other, other_student = seed_family(s.store, "f2", "200")
    items = seed_mcqs(s, family.id)
    item = seed_open_item(s.store, "other-item").model_copy(update={"family_id": other.id})
    s.store.put_item(item)
    await start_daily_session(s, family, student)
    await handle_answer(s, family, student, "1", 40, response_id="privacy")
    s.media.put(f"media/{family.id}/material", b"private material", "text/plain")
    s.media.put(f"media/{other.id}/material", b"other material", "text/plain")
    forget_family(s, family)
    assert s.store.get_family(family.id) is None
    assert s.grade_log.by_student(student.id) == []
    assert s.store.list_records(family.id) == []
    assert all(s.store.get_item(item.id) is None for item in items)
    assert s.media.get(f"media/{family.id}/material") is None
    assert s.store.get_student(other_student.id) is not None
    assert s.media.get(f"media/{other.id}/material") == b"other material"
