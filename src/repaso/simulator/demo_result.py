from collections import Counter
from dataclasses import dataclass, field

from repaso.core.orchestration.context import Services
from repaso.schemas.escalation import EscalationKind, EscalationStatus
from repaso.simulator.cohort import CohortLedger


@dataclass
class DemoClockResult:
    days: int
    students: int
    scheduled_days: int = 0
    sessions_delivered: int = 0
    responses: int = 0
    escalations_by_kind: Counter = field(default_factory=Counter)
    escalated_students: dict[str, set[str]] = field(default_factory=dict)
    quarantines_by_kind: Counter = field(default_factory=Counter)
    cohort_signals: list[str] = field(default_factory=list)
    cohort_weeks: Counter = field(default_factory=Counter)
    retired_items: list[str] = field(default_factory=list)
    planted_hedged: int = 0
    planted_injections: int = 0
    dropped_open_primes: int = 0
    struggle_fires: dict[str, list] = field(default_factory=dict)
    decisions: dict[str, set] = field(default_factory=dict)
    ledger: CohortLedger | None = None


def resolve_pending(services: Services) -> None:
    today = services.clock.today()
    for family in services.store.list_families():
        for escalation in services.store.list_pending_escalations(family.id):
            if escalation.created_at.date() < today:
                services.store.put_escalation(
                    escalation.model_copy(
                        update={
                            "status": EscalationStatus.RESOLVED,
                            "resolved_at": services.clock.now(),
                            "chosen_option": "guided_session",
                        }
                    )
                )


def collect_results(services: Services, result: DemoClockResult) -> None:
    for member in result.ledger.members:
        for escalation in services.store.list_escalations(member.family.id):
            result.escalations_by_kind[escalation.kind.value] += 1
            student = escalation.student_id or member.student.id
            result.escalated_students.setdefault(escalation.kind.value, set()).add(student)
            if escalation.kind is EscalationKind.STRUGGLE_TRIAGE:
                result.struggle_fires.setdefault(student, []).append(
                    escalation.created_at.date()
                )
        for quarantine in services.store.list_pending_quarantine(member.family.id):
            result.quarantines_by_kind[quarantine.kind.value] += 1
    for event in getattr(services.telemetry, "events", []):
        if event.kind == "decision" and event.student_id:
            result.decisions.setdefault(event.student_id, set()).add(event.name)
