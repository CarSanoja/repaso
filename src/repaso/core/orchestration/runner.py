from datetime import date
from uuid import uuid4

from repaso.core.orchestration.context import (
    CloseRun,
    EscalationRun,
    ExamRun,
    IngestRun,
    Services,
    TutorRun,
)
from repaso.core.orchestration.ingest_graph import build_ingest_graph
from repaso.core.orchestration.quality_graph import build_quality_graph
from repaso.core.orchestration.response_graph import build_response_graph
from repaso.core.orchestration.tutor_graph import build_session_graph
from repaso.i18n import msg
from repaso.schemas.channel import MediaKind, OutboundMessage
from repaso.schemas.escalation import Escalation, EscalationStatus
from repaso.schemas.family import Family
from repaso.schemas.grading import EvidenceSpan, StudentResponse
from repaso.schemas.material import Material
from repaso.schemas.provenance import Provenance, Source
from repaso.schemas.review import QuarantineItem, QuarantineKind
from repaso.schemas.schedule import ExamDate
from repaso.schemas.session import PracticeSession, SessionStatus
from repaso.schemas.student import Student

ACTIVE_SESSION_STATUSES = {SessionStatus.DELIVERED, SessionStatus.IN_PROGRESS}


def deliver_outbound(services: Services, messages: list[OutboundMessage]) -> list[str]:
    return [services.sender.send(message) for message in messages]


async def handle_material(
    services: Services,
    family: Family,
    student: Student,
    kind: MediaKind,
    data: bytes,
    material_id: str | None = None,
) -> IngestRun:
    material_id = material_id or uuid4().hex
    material = Material(
        id=material_id,
        family_id=family.id,
        kind=kind,
        media_ref=f"media/{family.id}/{material_id}",
        provenance=Provenance(source=Source.PARENT_UPLOAD, created_at=services.clock.now()),
    )
    services.media.put(material.media_ref, data, "application/octet-stream")
    run = IngestRun(family=family, student=student, material=material, data=data)
    await build_ingest_graph(services, run).invoke_async("ingest")
    deliver_outbound(services, run.outbound)
    return run


async def start_daily_session(services: Services, family: Family, student: Student) -> TutorRun:
    run = TutorRun(family=family, student=student)
    await build_session_graph(services, run).invoke_async("session")
    deliver_outbound(services, run.outbound)
    return run


def active_session(services: Services, student_id: str) -> PracticeSession | None:
    session = services.store.get_session_by_date(student_id, services.clock.today())
    if session is None or session.status not in ACTIVE_SESSION_STATUSES:
        return None
    return session


def current_item(services: Services, session: PracticeSession):
    if session.capsule is None:
        return None
    item_ids = session.capsule.item_ids
    if session.current_item_index >= len(item_ids):
        return None
    return services.store.get_item(item_ids[session.current_item_index])


async def handle_answer(
    services: Services,
    family: Family,
    student: Student,
    text: str,
    latency_seconds: float,
) -> TutorRun | None:
    verdict = services.screener.screen(text)
    if not verdict.safe:
        services.store.put_quarantine(
            QuarantineItem(
                id=uuid4().hex,
                kind=QuarantineKind.INJECTION_ATTEMPT,
                family_id=family.id,
                evidence=EvidenceSpan(quote=text[:200], source_ref=f"chat:{student.id}"),
                payload={"reasons": verdict.reasons, "student_id": student.id},
                created_at=services.clock.now(),
            )
        )
        return None
    session = active_session(services, student.id)
    if session is None:
        return None
    item = current_item(services, session)
    if item is None:
        return None
    response = StudentResponse(
        student_id=student.id,
        item_id=item.id,
        text=text,
        latency_seconds=latency_seconds,
        received_at=services.clock.now(),
    )
    run = TutorRun(family=family, student=student, session=session, items=[item], response=response)
    await build_response_graph(services, run).invoke_async("response")
    deliver_outbound(services, run.outbound)
    return run


async def run_daily_close(services: Services) -> CloseRun:
    run = CloseRun()
    await build_quality_graph(services, run).invoke_async("close")
    deliver_outbound(services, run.outbound)
    return run


def option_label(escalation: Escalation, option_key: str) -> str:
    for option in escalation.options:
        if option.key == option_key:
            return option.label
    return option_key


def resolve_escalation(
    services: Services, family: Family, escalation: Escalation, option_key: str
) -> EscalationRun:
    run = EscalationRun(family=family, escalation=escalation, chosen_option=option_key)
    if escalation.status is not EscalationStatus.PENDING:
        run.terminal = "already_resolved"
        return run
    run.escalation = escalation.model_copy(
        update={
            "status": EscalationStatus.RESOLVED,
            "chosen_option": option_key,
            "resolved_at": services.clock.now(),
        }
    )
    services.store.put_escalation(run.escalation)
    run.outbound.append(
        OutboundMessage(
            channel=family.channel,
            chat_ref=family.chat_ref,
            text=msg("escalation_ack", family.lang, option=option_label(escalation, option_key)),
        )
    )
    deliver_outbound(services, run.outbound)
    return run


def record_exam(services: Services, family: Family, exam_date: date, topic: str) -> ExamRun:
    students = services.store.list_students(family.id)
    for student in students:
        services.store.put_exam_date(
            ExamDate(student_id=student.id, competency_id=None, exam_date=exam_date)
        )
    return ExamRun(
        family=family,
        exam_date=exam_date,
        topic=topic,
        student_ids=[student.id for student in students],
        days_away=(exam_date - services.clock.today()).days,
    )
