from typing import Any

from repaso.core.orchestration.context import CloseRun, IngestRun, TutorRun
from repaso.schemas.channel import OutboundMessage
from repaso.schemas.grading import GradeResult


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
