from uuid import uuid4

from repaso.core.orchestration.context import Services
from repaso.core.orchestration.ingest_holds import QUOTE_LENGTH, held_kind, offered_reply
from repaso.core.orchestration.study_answer import current_item
from repaso.core.orchestration.study_flow import StudyReply
from repaso.core.orchestration.study_messages import plain, question, say
from repaso.schemas.family import Family
from repaso.schemas.grading import EvidenceSpan
from repaso.schemas.review import QuarantineItem
from repaso.schemas.student import Student
from repaso.schemas.study_session import StudySession
from repaso.tools.guardrails import ScreenVerdict


def hold_unsafe(
    services: Services,
    family: Family,
    student: Student,
    session: StudySession,
    verdict: ScreenVerdict,
    text: str,
) -> StudyReply:
    services.store.put_quarantine(
        QuarantineItem(
            id=uuid4().hex,
            kind=held_kind(verdict),
            family_id=family.id,
            evidence=EvidenceSpan(
                quote=services.screener.redact(text)[:QUOTE_LENGTH],
                source_ref=f"chat:{student.id}",
            ),
            payload={"reasons": verdict.reasons, "student_id": student.id},
            created_at=services.clock.now(),
        )
    )
    offered = offered_reply(verdict)
    if offered:
        return StudyReply([plain(family, offered)], session)
    messages = [say(family, "turn_blocked")]
    item = current_item(services, session)
    if item is not None:
        messages.append(question(family, session, item, len(session.progress.served)))
    return StudyReply(messages, session)
