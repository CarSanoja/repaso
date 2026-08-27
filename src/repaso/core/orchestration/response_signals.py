from repaso.core.orchestration.context import Services
from repaso.schemas.escalation import EscalationKind, EscalationStatus
from repaso.schemas.grading import EvidenceSpan

LATENCY_WINDOW = 20
EVIDENCE_SPANS = 3


def latency_window(services: Services, student_id: str, latest: float) -> list[float]:
    grades = services.grade_log.by_student(student_id)
    window = [g.latency_seconds for g in grades if g.latency_seconds is not None]
    return window[-LATENCY_WINDOW:] + [latest]


def days_since_struggle(services: Services, family_id: str, student_id: str) -> int | None:
    history = [
        e
        for e in services.store.list_escalations(family_id)
        if e.kind is EscalationKind.STRUGGLE_TRIAGE and e.student_id == student_id
    ]
    if not history:
        return None
    if any(e.status is EscalationStatus.PENDING for e in history):
        return 0
    latest = max(e.created_at for e in history)
    return (services.clock.today() - latest.date()).days


def struggle_evidence(
    services: Services,
    student_id: str,
    competency_id: str,
    fallback: EvidenceSpan,
) -> list[EvidenceSpan]:
    spans = []
    for grade in reversed(services.grade_log.by_student(student_id)):
        if grade.correct is False:
            item = services.store.get_item(grade.item_id)
            if item is not None and item.competency_id == competency_id:
                spans.append(grade.evidence)
        if len(spans) == EVIDENCE_SPANS:
            break
    return list(reversed(spans)) or [fallback]
