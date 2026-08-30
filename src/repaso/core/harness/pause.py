from repaso.core.telemetry.sink import TelemetrySink
from repaso.schemas.family import Family, FamilyStatus

TRACE_KIND = "family"
TRACE_NAME = "paused"
TRACE_STATUS = "skipped"


def is_paused(family: Family) -> bool:
    return family.status is FamilyStatus.PAUSED


def trace_paused(
    telemetry: TelemetrySink, family: Family, step: str, student_id: str | None = None
) -> None:
    telemetry.trace(
        TRACE_KIND,
        TRACE_NAME,
        status=TRACE_STATUS,
        family_id=family.id,
        student_id=student_id,
        step=step,
    )
