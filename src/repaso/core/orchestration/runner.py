from datetime import date
from hashlib import sha256
from uuid import uuid4

from repaso.core.harness.pause import is_paused, trace_paused
from repaso.core.orchestration.adaptations import apply_adaptation
from repaso.core.orchestration.context import (
    CloseRun,
    EscalationRun,
    ExamRun,
    IngestRun,
    Services,
    TutorRun,
)
from repaso.core.orchestration.ingest_graph import build_ingest_graph
from repaso.core.orchestration.outbox import deliver
from repaso.core.orchestration.quality_graph import build_quality_graph
from repaso.core.orchestration.response_graph import build_response_graph
from repaso.core.orchestration.tutor_graph import build_session_graph
from repaso.i18n import msg
from repaso.schemas.channel import MediaKind, OutboundMessage
from repaso.schemas.escalation import Escalation, EscalationStatus
from repaso.schemas.family import Family
from repaso.schemas.grading import EvidenceSpan, GradeResult, StudentResponse
from repaso.schemas.material import Material
from repaso.schemas.operation import OperationRecord
from repaso.schemas.provenance import Provenance, Source
from repaso.schemas.review import QuarantineItem, QuarantineKind
from repaso.schemas.schedule import ExamDate
from repaso.schemas.session import PracticeSession, SessionStatus
from repaso.schemas.student import Student

ACTIVE_SESSION_STATUSES = {SessionStatus.DELIVERED, SessionStatus.IN_PROGRESS}


def deliver_outbound(
    services: Services,
    messages: list[OutboundMessage],
    key: str | None = None,
    scope: str | None = None,
) -> list[str]:
    return deliver(services, messages, key, scope)


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
    deliver_outbound(services, run.outbound, f"material#{material_id}", family.id)
    return run


async def start_daily_session(services: Services, family: Family, student: Student) -> TutorRun:
    run = TutorRun(family=family, student=student)
    if is_paused(family):
        run.terminal = "paused"
        trace_paused(services.telemetry, family, "daily_session", student.id)
        return run
    await build_session_graph(services, run).invoke_async("session")
    if run.session and run.outbound:
        deliver_outbound(services, run.outbound, f"session#{run.session.id}", family.id)
        run.session = run.session.model_copy(
            update={
                "status": SessionStatus.DELIVERED,
                "delivered_at": services.clock.now(),
            }
        )
        services.store.put_session(run.session)
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
    response_id: str | None = None,
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
    saved = services.store.get_record(family.id, f"answer#{response_id}") if response_id else None
    session = (
        PracticeSession.model_validate(saved.payload["session"])
        if saved
        else active_session(services, student.id)
    )
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
    response_id = (
        response_id or sha256(f"{session.id}:{session.current_item_index}".encode()).hexdigest()
    )
    key = f"answer#{response_id}"
    saved = saved or services.store.get_record(family.id, key)
    if saved is None:
        pending = [
            r
            for r in services.store.list_records(family.id, "answer#")
            if r.payload.get("student_id") == student.id and not r.payload.get("complete")
        ]
        if pending:
            raise RuntimeError("previous answer is awaiting recovery")
        saved = OperationRecord(
            scope=family.id,
            key=key,
            payload={
                "session": session.model_dump(mode="json"),
                "student_id": student.id,
                "response": response.model_dump(mode="json"),
            },
        )
        services.store.put_record(saved)
    run.operation = saved
    run.response = StudentResponse.model_validate(saved.payload["response"])
    if saved.payload.get("complete"):
        run.session = PracticeSession.model_validate(saved.payload["final_session"])
        run.grade = GradeResult.model_validate(saved.payload["grade"])
        run.outbound = [OutboundMessage.model_validate(m) for m in saved.payload["outbound"]]
        run.decision_action = saved.payload.get("decision")
        run.escalations = [
            Escalation.model_validate(e) for e in saved.payload.get("escalations", [])
        ]
    else:
        await build_response_graph(services, run).invoke_async("response")
        saved.payload.update(
            {
                "complete": True,
                "final_session": run.session.model_dump(mode="json"),
                "outbound": [m.model_dump(mode="json") for m in run.outbound],
                "escalations": [e.model_dump(mode="json") for e in run.escalations],
            }
        )
        services.store.put_record(saved)
    deliver_outbound(services, run.outbound, key, family.id)
    return run


async def run_daily_close(services: Services) -> CloseRun:
    run = CloseRun()
    await build_quality_graph(services, run).invoke_async("close")
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
    if escalation.family_id != family.id:
        raise ValueError("escalation does not belong to family")
    escalation = services.store.get_escalation(escalation.id) or escalation
    if escalation.status is not EscalationStatus.PENDING:
        run.terminal = "already_resolved"
        return run
    if option_key not in {o.key for o in escalation.options}:
        raise ValueError("option is not available for this escalation")
    key = f"escalation-decision#{escalation.id}"
    saved = services.store.get_record(family.id, key)
    if saved is None:
        saved = OperationRecord(scope=family.id, key=key, payload={"option": option_key})
        services.store.put_record(saved)
    option_key = saved.payload["option"]
    run.chosen_option = option_key
    if option_key == "teacher_note":
        note = escalation.drafted_note or escalation.summary
        run.outbound.append(
            OutboundMessage(channel=family.channel, chat_ref=family.chat_ref, text=note)
        )
    elif option_key == "reduce_load":
        if not escalation.student_id or not escalation.competency_id:
            raise ValueError("load reduction requires a student and competency")
        apply_adaptation(
            services,
            family,
            escalation.student_id,
            escalation.competency_id,
            "reduce_load",
            source=f"escalation:{escalation.id}",
        )
    else:
        raise ValueError("this option is not implemented")
    run.escalation = escalation.model_copy(
        update={
            "status": EscalationStatus.RESOLVED,
            "chosen_option": option_key,
            "resolved_at": services.clock.now(),
        }
    )
    run.outbound.append(
        OutboundMessage(
            channel=family.channel,
            chat_ref=family.chat_ref,
            text=msg("escalation_ack", family.lang, option=option_label(escalation, option_key)),
        )
    )
    deliver_outbound(services, run.outbound, f"escalation#{escalation.id}", family.id)
    services.store.put_escalation(run.escalation)
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
