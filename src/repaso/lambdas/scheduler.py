import logging
from typing import Any
from zoneinfo import ZoneInfo

from repaso.config.settings import get_settings
from repaso.core.harness.calendar import is_scheduled
from repaso.core.harness.clock import SystemClock
from repaso.core.harness.idempotency import job_key
from repaso.core.harness.pause import is_paused
from repaso.lambdas.bootstrap import publisher, store
from repaso.schemas.common import FamilyId
from repaso.schemas.events import DomainEvent, EventKind
from repaso.schemas.operation import OperationRecord

FAMILY_KEY = "family_id"
STUDENT_KEY = "student_id"
JOB_KIND = "daily_session"
OWNER = "scheduler-tick"

logger = logging.getLogger(__name__)


def _text(tick: dict[str, Any], key: str) -> str:
    value = tick.get(key)
    return value.strip() if isinstance(value, str) else ""


def _paused(family_id: str) -> bool:
    family = store().get_family(FamilyId(family_id))
    return family is not None and is_paused(family)


def _students(family_id: str, student_id: str) -> list[str]:
    if student_id:
        return [student_id]
    return [student.id for student in store().list_students(FamilyId(family_id))]


def _fire(family_id: str, student_id: str, day: str, now: Any) -> str:
    key = job_key(JOB_KIND, student_id, day)
    if store().get_record(family_id, key):
        logger.info("scheduler tick already fired for %s", key)
        return ""
    publisher().publish(
        DomainEvent(
            kind=EventKind.DAILY_SESSION_DUE,
            family_id=FamilyId(family_id),
            idempotency_key=key,
            occurred_at=now,
            payload={STUDENT_KEY: student_id},
        )
    )
    store().put_record(OperationRecord(scope=family_id, key=key, payload={"published": True}))
    return key


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    tick = event if isinstance(event, dict) else {}
    if tick.get("kind") == "daily_close":
        now = SystemClock().now()
        day = now.astimezone(ZoneInfo("America/Caracas")).date().isoformat()
        publisher().publish(
            DomainEvent(
                kind=EventKind.DAILY_CLOSE,
                family_id=None,
                idempotency_key=f"close#{day}",
                occurred_at=now,
                payload={},
            )
        )
        return {"ok": True, "kind": "daily_close"}
    family_id = _text(tick, FAMILY_KEY)
    if not family_id:
        logger.error("scheduler tick arrived without a family reference")
        return {"ok": False, "error": "missing_family_id"}
    family = store().get_family(FamilyId(family_id))
    if family is None:
        return {"ok": True, "fired": [], "skipped": [], "forgotten": True}
    if _paused(family_id):
        logger.info("scheduler tick skipped: family %s is paused", family_id)
        return {"ok": True, "family_id": family_id, "fired": [], "skipped": [], "paused": True}
    now = SystemClock().now()
    local_day = now.astimezone(ZoneInfo(family.timezone)).date()
    if not is_scheduled(local_day, family.rest_weekdays, get_settings().holiday_dates):
        return {"ok": True, "fired": [], "skipped": [], "rest_day": True}
    day = local_day.isoformat()
    fired: list[str] = []
    skipped: list[str] = []
    for student_id in _students(family_id, _text(tick, STUDENT_KEY)):
        student = store().get_student(student_id)
        if student is None or student.family_id != family_id:
            skipped.append(student_id)
            continue
        try:
            key = _fire(family_id, student_id, day, now)
        except ValueError:
            logger.error("scheduler tick carried an unusable student reference")
            skipped.append(student_id)
            continue
        (fired if key else skipped).append(student_id)
    return {"ok": True, "family_id": family_id, "fired": fired, "skipped": skipped}
