from repaso.agents.capsule_composer import answer_ref
from repaso.core.orchestration.context import Services
from repaso.core.orchestration.runner import active_session
from repaso.core.orchestration.runner import current_item as capsule_item
from repaso.core.orchestration.study_flow import (
    StudyReply,
    answer_sitting,
    close_sitting,
    current_item,
    resume_sitting,
    start_sitting,
)
from repaso.core.orchestration.study_messages import say
from repaso.core.orchestration.study_store import open_sitting
from repaso.schemas.family import Family
from repaso.schemas.student import Student
from repaso.schemas.study_session import Actor, StudySessionStatus

SESSION_COMMANDS = frozenset({"/sesion", "/sesión", "/session"})
TOPIC_COMMANDS = frozenset({"/tema", "/topic"})
CLOSE_COMMANDS = frozenset({"/listo", "/done"})
STUDY_COMMANDS = SESSION_COMMANDS | TOPIC_COMMANDS | CLOSE_COMMANDS
CALLBACK_PARTS = 3


def study_student(services: Services, family: Family) -> Student | None:
    students = services.store.list_students(family.id)
    return students[0] if len(students) == 1 else None


def _capsule_waiting(services: Services, student: Student) -> bool:
    session = active_session(services, student.id)
    return session is not None and capsule_item(services, session) is not None


def handle_study_command(services: Services, family: Family, text: str) -> StudyReply | None:
    head, _, argument = text.strip().partition(" ")
    command = head.split("@")[0].casefold()
    if command not in STUDY_COMMANDS:
        return None
    student = study_student(services, family)
    if student is None:
        return StudyReply([say(family, "study_one_child")])
    sitting = open_sitting(services, family, student)
    if command in CLOSE_COMMANDS:
        if sitting is None:
            return StudyReply([say(family, "study_none_open")])
        return close_sitting(services, family, sitting, Actor.FAMILY)
    if command in TOPIC_COMMANDS:
        topic = argument.strip()
        if not topic:
            return StudyReply([say(family, "study_ask_topic")])
        if sitting is not None:
            close_sitting(services, family, sitting, Actor.FAMILY)
        return start_sitting(services, family, student, topic)
    if sitting is not None:
        return resume_sitting(services, family, student, sitting)
    return start_sitting(services, family, student)


def handle_study_text(
    services: Services, family: Family, text: str, latency_seconds: float
) -> StudyReply | None:
    student = study_student(services, family)
    if student is None:
        return None
    sitting = open_sitting(services, family, student)
    if sitting is None:
        return None
    if sitting.status is StudySessionStatus.ACTIVE:
        return answer_sitting(services, family, student, sitting, text, latency_seconds)
    if _capsule_waiting(services, student):
        return None
    return resume_sitting(services, family, student, sitting)


def handle_study_callback(
    services: Services, family: Family, data: str, latency_seconds: float
) -> StudyReply | None:
    parts = data.split(":")
    if len(parts) != CALLBACK_PARTS or not parts[-1].isdigit():
        return None
    student = study_student(services, family)
    if student is None:
        return StudyReply([say(family, "study_one_child")])
    sitting = open_sitting(services, family, student)
    chosen = _chosen_option(services, sitting, parts)
    if chosen is None:
        return StudyReply([say(family, "study_stale_button")])
    return answer_sitting(services, family, student, sitting, chosen, latency_seconds)


def _chosen_option(services: Services, sitting, parts: list[str]) -> str | None:
    if sitting is None or sitting.status is not StudySessionStatus.ACTIVE:
        return None
    item = current_item(services, sitting)
    if item is None or parts[1] != answer_ref(sitting.id, item.id):
        return None
    index = int(parts[-1]) - 1
    if not 0 <= index < len(item.options):
        return None
    return item.options[index]
