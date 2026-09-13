from datetime import datetime

from repaso.core.orchestration import turn_memory
from repaso.core.orchestration.context import Services
from repaso.core.orchestration.runner import active_session
from repaso.core.orchestration.turn_replies import TurnTarget, topic
from repaso.schemas.family import Family
from repaso.schemas.item import Item
from repaso.schemas.session import PracticeSession, SessionStatus
from repaso.schemas.student import Student
from repaso.schemas.turn import PracticeState, TurnContext, TurnWindow

OPEN_STATUSES = {SessionStatus.DELIVERED, SessionStatus.IN_PROGRESS}
NO_WINDOW = TurnWindow(session_id="")


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
