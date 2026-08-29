import logging
from typing import Any

from repaso.core.harness.clock import SystemClock
from repaso.core.harness.idempotency import job_key
from repaso.lambdas.bootstrap import publisher, store
from repaso.schemas.common import FamilyId
from repaso.schemas.events import DomainEvent, EventKind

FAMILY_KEY = "family_id"
STUDENT_KEY = "student_id"
JOB_KIND = "daily_session"
OWNER = "scheduler-tick"

logger = logging.getLogger(__name__)


def _text(tick: dict[str, Any], key: str) -> str:
    value = tick.get(key)
    return value.strip() if isinstance(value, str) else ""


def _students(family_id: str, student_id: str) -> list[str]:
    if student_id:
        return [student_id]
    return [student.id for student in store().list_students(FamilyId(family_id))]


def _fire(family_id: str, student_id: str, day: str, now: Any) -> str:
    key = job_key(JOB_KIND, student_id, day)
    if not store().claim(key, OWNER):
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
    return key


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    tick = event if isinstance(event, dict) else {}
    family_id = _text(tick, FAMILY_KEY)
    if not family_id:
        logger.error("scheduler tick arrived without a family reference")
        return {"ok": False, "error": "missing_family_id"}
    now = SystemClock().now()
    day = now.date().isoformat()
    fired: list[str] = []
    skipped: list[str] = []
    for student_id in _students(family_id, _text(tick, STUDENT_KEY)):
        try:
            key = _fire(family_id, student_id, day, now)
        except ValueError:
            logger.error("scheduler tick carried an unusable student reference")
            skipped.append(student_id)
            continue
        (fired if key else skipped).append(student_id)
    return {"ok": True, "family_id": family_id, "fired": fired, "skipped": skipped}
