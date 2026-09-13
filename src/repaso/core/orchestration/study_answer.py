from repaso.agents.grader import grade_mcq, normalize
from repaso.core.harness.study_session import record_answer
from repaso.core.orchestration.answer_outcome import record_answer_outcome
from repaso.core.orchestration.context import Services
from repaso.core.orchestration.study_flow import StudyReply, serve_next
from repaso.core.orchestration.study_messages import question, say
from repaso.schemas.channel import OutboundMessage
from repaso.schemas.family import Family
from repaso.schemas.grading import StudentResponse
from repaso.schemas.item import Item
from repaso.schemas.student import Student
from repaso.schemas.study_session import StudySession


def current_item(services: Services, session: StudySession) -> Item | None:
    if not session.progress.served:
        return None
    return services.store.get_item(session.progress.served[-1])


def picked_option(item: Item, text: str) -> str | None:
    reply = normalize(text)
    options = [normalize(option) for option in item.options]
    if reply in options:
        return item.options[options.index(reply)]
    if reply.isdigit() and 1 <= int(reply) <= len(options):
        return item.options[int(reply) - 1]
    return None


def answer_key_for(session: StudySession) -> str:
    return f"{session.id}:{max(0, len(session.progress.served) - 1)}"


def _feedback(family: Family, item: Item, correct: bool) -> OutboundMessage:
    key = "study_right" if correct else "study_wrong"
    return say(family, key, answer=item.answer_key, rationale=item.rationale.strip())


def answer_sitting(
    services: Services,
    family: Family,
    student: Student,
    session: StudySession,
    text: str,
    latency_seconds: float,
) -> StudyReply:
    item = current_item(services, session)
    if item is None:
        return serve_next(services, family, student, session, StudyReply())
    asked = len(session.progress.served)
    key = answer_key_for(session)
    if key in session.progress.answered_keys:
        return StudyReply([question(family, session, item, asked)], session)
    if picked_option(item, text) is None:
        unread = say(family, "study_not_an_answer")
        return StudyReply([unread, question(family, session, item, asked)], session)
    now = services.clock.now()
    response = StudentResponse(
        student_id=student.id,
        item_id=item.id,
        text=text,
        latency_seconds=latency_seconds,
        received_at=now,
    )
    grade = grade_mcq(item, response, now)
    grade.id = f"study:{key}"
    grade.responded_at = now
    services.grade_log.append(grade)
    correct = bool(grade.correct)
    record_answer_outcome(services, student.id, item, correct, latency_seconds, f"study:{key}")
    answered = record_answer(session, key, correct, now)
    said = StudyReply([_feedback(family, item, correct)])
    return serve_next(services, family, student, answered, said)
