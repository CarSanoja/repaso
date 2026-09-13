from datetime import datetime
from uuid import uuid4

from repaso.agents.grader import normalize
from repaso.agents.turn_reader import read_turn
from repaso.config.models import ModelRole
from repaso.core.orchestration import turn_memory
from repaso.core.orchestration.context import ChannelRun, Route, Services
from repaso.core.orchestration.ingest_holds import QUOTE_LENGTH, held_kind
from repaso.core.orchestration.runner import (
    active_session,
    current_item,
    handle_answer,
)
from repaso.core.orchestration.turn_replies import TurnTarget, reply_to, speak, topic
from repaso.schemas.family import Family
from repaso.schemas.grading import EvidenceSpan
from repaso.schemas.item import Item, ItemKind
from repaso.schemas.review import QuarantineItem
from repaso.schemas.session import PracticeSession, SessionStatus
from repaso.schemas.student import Student
from repaso.schemas.turn import (
    PracticeState,
    TurnContext,
    TurnDecision,
    TurnIntent,
    TurnWindow,
)
from repaso.tools.guardrails import ScreenVerdict

READ_ROLE = ModelRole.CLASSIFY
OPEN_STATUSES = {SessionStatus.DELIVERED, SessionStatus.IN_PROGRESS}
NO_WINDOW = TurnWindow(session_id="")


async def route_turn(services: Services, run: ChannelRun, family: Family, text: str) -> None:
    verdict = services.screener.screen(text)
    if not verdict.safe:
        hold_blocked(services, run, family, verdict, text)
        return
    said = services.screener.redact(text)
    target = build_target(services, family, run.message.message_ref)
    run.student = target.student
    decision = await read_turn(
        said, turn_context(services, family, target), services.model(READ_ROLE)
    )
    if decision is None:
        run.route = Route.CONVERSATION
        speak(run, family, "turn_not_understood")
        return
    services.telemetry.trace(
        "turn",
        decision.intent.value,
        family_id=family.id,
        student_id=target.student.id if target.student else None,
    )
    if decision.intent is TurnIntent.ANSWER and target.state is PracticeState.OPEN:
        await route_answer(services, run, family, answer_for(target.item, decision, text))
        return
    await reply_to(services, run, family, target, decision, said)


async def route_answer(services: Services, run: ChannelRun, family: Family, text: str) -> None:
    student = answering_student(services, family)
    if student is None:
        run.route = Route.IGNORED
        return
    run.student = student
    run.route = Route.ANSWER
    session = active_session(services, student.id)
    item = current_item(services, session)
    index = session.current_item_index
    run.tutor = await handle_answer(
        services,
        family,
        student,
        text,
        latency(services, student.id, run.message.received_at),
        response_id=f"chat:{run.message.message_ref}",
    )
    remember_answer(services, run, family, item, index, text)


def remember_answer(
    services: Services,
    run: ChannelRun,
    family: Family,
    item: Item | None,
    index: int,
    text: str,
) -> None:
    tutor = run.tutor
    if tutor is None or tutor.session is None:
        return
    if tutor.grade is not None:
        turn_memory.remember(
            services,
            family.id,
            tutor.session.id,
            turn_memory.note(
                turn_id=run.message.message_ref,
                intent=TurnIntent.ANSWER,
                at=services.clock.now(),
                item=item,
                item_index=index,
                said=services.screener.redact(text),
                correct=tutor.grade.correct,
            ),
        )
    if tutor.session.status is SessionStatus.COMPLETED:
        turn_memory.close_window(services, family.id, tutor.session.id)


def build_target(services: Services, family: Family, turn_id: str) -> TurnTarget:
    student = focus_student(services, family)
    session = today_session(services, student)
    item, index = focus_item(services, session)
    window = (
        turn_memory.read_window(services, family.id, session.id)
        if session is not None
        else NO_WINDOW
    )
    return TurnTarget(
        turn_id=turn_id,
        state=practice_state(session),
        window=window,
        student=student,
        session=session,
        item=item,
        item_index=index,
        answered=was_answered(session, index),
        competency=(
            services.retriever.get_competency(item.competency_id) if item is not None else None
        ),
    )


def turn_context(services: Services, family: Family, target: TurnTarget) -> TurnContext:
    return TurnContext(
        lang=family.lang,
        grade=target.student.grade if target.student else 0,
        competency=topic(target, family),
        practice=target.state,
        question=target.item.stem if target.item else "",
        options=list(target.item.options) if target.item else [],
        items_left=items_left(target.session),
        answered=target.answered,
        history=turn_memory.history_lines(services, target.window),
    )


def was_answered(session: PracticeSession | None, index: int) -> bool:
    if session is None:
        return False
    return index < session.current_item_index or session.status is SessionStatus.COMPLETED


def practice_state(session: PracticeSession | None) -> PracticeState:
    if session is None or session.capsule is None or session.status is SessionStatus.PLANNED:
        return PracticeState.NOT_SENT
    return PracticeState.OPEN if session.status in OPEN_STATUSES else PracticeState.FINISHED


def today_session(services: Services, student: Student | None) -> PracticeSession | None:
    if student is None:
        return None
    return services.store.get_session_by_date(student.id, services.clock.today())


def focus_item(services: Services, session: PracticeSession | None) -> tuple[Item | None, int]:
    if session is None or session.capsule is None or not session.capsule.item_ids:
        return None, 0
    item_ids = session.capsule.item_ids
    index = min(session.current_item_index, len(item_ids) - 1)
    return services.store.get_item(item_ids[index]), index


def items_left(session: PracticeSession | None) -> int:
    if session is None or session.capsule is None:
        return 0
    return max(0, len(session.capsule.item_ids) - session.current_item_index - 1)


def names_an_option(item: Item, candidate: str) -> bool:
    options = [normalize(option) for option in item.options]
    chosen = normalize(candidate)
    if chosen in options:
        return True
    return chosen.isdigit() and 1 <= int(chosen) <= len(options)


def answer_for(item: Item | None, decision: TurnDecision, text: str) -> str:
    candidate = decision.answer_text.strip()
    if not candidate or item is None or item.kind is not ItemKind.MCQ:
        return text
    return candidate if names_an_option(item, candidate) else text


def focus_student(services: Services, family: Family) -> Student | None:
    students = services.store.list_students(family.id)
    answering = [student for student in students if active_session(services, student.id)]
    if answering:
        return answering[0]
    return students[0] if len(students) == 1 else None


def answering_student(services: Services, family: Family) -> Student | None:
    for student in services.store.list_students(family.id):
        if active_session(services, student.id) is not None:
            return student
    return None


def latency(services: Services, student_id: str, received_at: datetime) -> float:
    session = active_session(services, student_id)
    if session is None or session.delivered_at is None:
        return 0.0
    return max(0.0, (received_at - session.delivered_at).total_seconds())


def hold_blocked(
    services: Services, run: ChannelRun, family: Family, verdict: ScreenVerdict, text: str
) -> None:
    run.route = Route.CONVERSATION
    student = focus_student(services, family)
    services.store.put_quarantine(
        QuarantineItem(
            id=uuid4().hex,
            kind=held_kind(verdict),
            family_id=family.id,
            evidence=EvidenceSpan(
                quote=services.screener.redact(text)[:QUOTE_LENGTH],
                source_ref=f"chat:{student.id if student else family.chat_ref}",
            ),
            payload={"reasons": verdict.reasons, "student_id": student.id if student else ""},
            created_at=services.clock.now(),
        )
    )
    speak(run, family, "turn_blocked")
