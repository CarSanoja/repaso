from typing import Any

from repaso.core.orchestration.context import (
    ChannelRun,
    CloseRun,
    EscalationRun,
    ExamRun,
    IngestRun,
    QuarantineRun,
    TutorRun,
)
from repaso.schemas.channel import OutboundMessage
from repaso.schemas.grading import GradeResult
from repaso.schemas.study_session import StudySession


def outbound_summary(messages: list[OutboundMessage]) -> list[dict[str, Any]]:
    return [
        {"channel": message.channel.value, "chat_ref": message.chat_ref, "text": message.text}
        for message in messages
    ]


def grade_summary(grade: GradeResult | None) -> dict[str, Any] | None:
    if grade is None:
        return None
    return {
        "item_id": grade.item_id,
        "correct": grade.correct,
        "confidence": grade.confidence,
        "graded_by": grade.graded_by.value,
        "quarantined": grade.quarantined,
    }


def ingest_summary(run: IngestRun) -> dict[str, Any]:
    return {
        "handled": True,
        "material_id": run.material.id,
        "terminal": run.terminal,
        "competency_id": run.competency.id if run.competency is not None else None,
        "generated": len(run.generated),
        "kept_item_ids": [item.id for item in run.kept],
        "outbound": outbound_summary(run.outbound),
    }


def tutor_summary(run: TutorRun | None) -> dict[str, Any]:
    if run is None:
        return {"handled": False, "outbound": []}
    session = run.session
    return {
        "handled": True,
        "terminal": run.terminal,
        "session_id": session.id if session is not None else None,
        "session_status": session.status.value if session is not None else None,
        "decision_action": run.decision_action,
        "grade": grade_summary(run.grade),
        "escalations": [escalation.kind.value for escalation in run.escalations],
        "outbound": outbound_summary(run.outbound),
    }


def close_summary(run: CloseRun) -> dict[str, Any]:
    return {
        "handled": True,
        "report": run.report.model_dump(mode="json") if run.report is not None else None,
        "cohort_fired": list(run.cohort_fired),
        "retired_items": list(run.retired_items),
        "outbound": outbound_summary(run.outbound),
    }


def study_summary(session: StudySession | None) -> dict[str, Any] | None:
    if session is None:
        return None
    return {
        "session_id": session.id,
        "status": session.status.value,
        "competency_id": session.goal.competency_id,
        "asked": len(session.progress.served),
        "correct": session.progress.correct,
        "closed_reason": session.closed_reason.value if session.closed_reason else None,
    }


def channel_summary(run: ChannelRun) -> dict[str, Any]:
    if run.replayed_summary is not None:
        return run.replayed_summary
    return {
        "handled": True,
        "route": run.route.value,
        "family_id": run.family.id if run.family is not None else None,
        "student_id": run.student.id if run.student is not None else None,
        "events": [event.kind.value for event in run.events],
        "ingest": ingest_summary(run.ingest) if run.ingest is not None else None,
        "tutor": tutor_summary(run.tutor) if run.tutor is not None else None,
        "study": study_summary(run.study),
        "outbound": outbound_summary(run.outbound),
    }


def escalation_summary(run: EscalationRun) -> dict[str, Any]:
    return {
        "handled": run.terminal is None,
        "terminal": run.terminal,
        "escalation_id": run.escalation.id,
        "status": run.escalation.status.value,
        "chosen_option": run.escalation.chosen_option,
        "outbound": outbound_summary(run.outbound),
    }


def quarantine_summary(run: QuarantineRun) -> dict[str, Any]:
    return {
        "handled": run.terminal is None,
        "terminal": run.terminal,
        "quarantine_id": run.quarantine.id,
        "status": run.quarantine.status.value,
        "released_item_id": run.released_item_id,
        "outbound": outbound_summary(run.outbound),
    }


def exam_summary(run: ExamRun) -> dict[str, Any]:
    return {
        "handled": True,
        "exam_date": run.exam_date.isoformat(),
        "topic": run.topic,
        "student_ids": list(run.student_ids),
        "days_away": run.days_away,
        "outbound": [],
    }
