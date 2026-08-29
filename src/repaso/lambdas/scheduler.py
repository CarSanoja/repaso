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


def _text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    return value.strip() if isinstance(value, str) else ""


def _due_payload(tick: dict[str, Any], family_id: str) -> dict[str, Any]:
    payload: dict[str, Any] = {FAMILY_KEY: family_id}
    student_id = _text(tick, STUDENT_KEY)
    if student_id:
        payload[STUDENT_KEY] = student_id
    return payload


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    tick = event if isinstance(event, dict) else {}
    family_id = _text(tick, FAMILY_KEY)
    if not family_id:
        logger.error("scheduler tick arrived without a family reference")
        return {"ok": False, "error": "missing_family_id"}
    now = SystemClock().now()
    try:
        key = job_key(JOB_KIND, family_id, now.date().isoformat())
    except ValueError:
        logger.error("scheduler tick carried an unusable family reference")
        return {"ok": False, "error": "invalid_family_id"}
    if not store().claim(key, OWNER):
        logger.info("scheduler tick already fired for %s", key)
        return {"ok": True, "duplicate": True, "idempotency_key": key}
    publisher().publish(
        DomainEvent(
            kind=EventKind.DAILY_SESSION_DUE,
            family_id=FamilyId(family_id),
            idempotency_key=key,
            occurred_at=now,
            payload=_due_payload(tick, family_id),
        )
    )
    return {"ok": True, "duplicate": False, "idempotency_key": key}
