from datetime import datetime, timedelta
from numbers import Number
from typing import Any

from repaso.schemas.operation import OperationRecord

ANSWER_RETENTION_DAYS = 7
TTL_ATTRIBUTE = "expires_at"


def expiry_stamp(now: datetime, days: int = ANSWER_RETENTION_DAYS) -> int:
    return int((now + timedelta(days=days)).timestamp())


def expiry_of(payload: dict[str, Any]) -> float | None:
    stamp = payload.get(TTL_ATTRIBUTE)
    if isinstance(stamp, bool) or not isinstance(stamp, Number):
        return None
    return float(stamp)


def expired(record: OperationRecord, now: datetime) -> bool:
    stamp = expiry_of(record.payload)
    return stamp is not None and stamp <= now.timestamp()
