import json
import logging
from typing import Any

from repaso.core.harness.idempotency import KEY_SEPARATOR
from repaso.lambdas.bootstrap import store
from repaso.schemas.events import DomainEvent

BATCH_FAILURES_KEY = "batchItemFailures"
ITEM_IDENTIFIER_KEY = "itemIdentifier"
DETAIL_KEY = "detail"
RECORDS_KEY = "Records"
MESSAGE_ID_KEY = "messageId"
BODY_KEY = "body"
OWNER = "sqs-worker"
WORKER_KEY_PREFIX = "worker"

logger = logging.getLogger(__name__)


def worker_key(event: DomainEvent) -> str:
    return KEY_SEPARATOR.join((WORKER_KEY_PREFIX, event.kind.value, event.idempotency_key))


def decode(record: dict[str, Any]) -> DomainEvent:
    body = json.loads(record[BODY_KEY])
    detail = body.get(DETAIL_KEY, body) if isinstance(body, dict) else body
    return DomainEvent.model_validate(detail)


def _dispatch(event: DomainEvent) -> Any:
    from repaso.runtime.entrypoint import invoke

    return invoke(event.model_dump(mode="json"))


def _process(record: dict[str, Any]) -> None:
    event = decode(record)
    key = worker_key(event)
    if not store().claim(key, OWNER):
        logger.info("worker skipped an already claimed event %s", key)
        return
    _dispatch(event)


def _identifier(record: Any) -> str:
    if not isinstance(record, dict):
        return ""
    value = record.get(MESSAGE_ID_KEY)
    return value if isinstance(value, str) else ""


def handler(event: dict[str, Any], context: Any = None) -> dict[str, list[dict[str, str]]]:
    records = event.get(RECORDS_KEY) if isinstance(event, dict) else None
    failures: list[dict[str, str]] = []
    for record in records or []:
        identifier = _identifier(record)
        try:
            _process(record)
        except Exception:
            logger.exception("worker failed on message %s", identifier or "<unidentified>")
            if identifier:
                failures.append({ITEM_IDENTIFIER_KEY: identifier})
    return {BATCH_FAILURES_KEY: failures}
