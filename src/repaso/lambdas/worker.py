import json
import logging
from typing import Any

from repaso.core.harness.idempotency import KEY_SEPARATOR
from repaso.lambdas.bootstrap import store
from repaso.schemas.events import DomainEvent

BATCH_FAILURES_KEY = "batchItemFailures"
ITEM_IDENTIFIER_KEY = "itemIdentifier"
RECORDS_KEY = "Records"
MESSAGE_ID_KEY = "messageId"
ATTRIBUTES_KEY = "attributes"
RECEIVE_COUNT_KEY = "ApproximateReceiveCount"
BODY_KEY = "body"
DETAIL_KEY = "detail"
OK_KEY = "ok"
ERROR_KEY = "error"
CODE_KEY = "code"
FIRST_DELIVERY = "1"
UNREADABLE_RESULT = "unreadable_result"
OWNER = "sqs-worker"
WORKER_KEY_PREFIX = "worker"

logger = logging.getLogger(__name__)


def worker_key(event: DomainEvent) -> str:
    return KEY_SEPARATOR.join((WORKER_KEY_PREFIX, event.kind.value, event.idempotency_key))


def decode(record: dict[str, Any]) -> DomainEvent:
    body = json.loads(record[BODY_KEY])
    detail = body.get(DETAIL_KEY, body) if isinstance(body, dict) else body
    return DomainEvent.model_validate(detail)


def first_delivery(record: dict[str, Any]) -> bool:
    attributes = record.get(ATTRIBUTES_KEY)
    if not isinstance(attributes, dict):
        return True
    return str(attributes.get(RECEIVE_COUNT_KEY, FIRST_DELIVERY)) == FIRST_DELIVERY


def _dispatch(event: DomainEvent) -> Any:
    from repaso.runtime.entrypoint import invoke

    return invoke(event.model_dump(mode="json"))


def _reason(result: Any) -> str:
    if isinstance(result, dict):
        error = result.get(ERROR_KEY)
        if isinstance(error, dict):
            return str(error.get(CODE_KEY, UNREADABLE_RESULT))
    return UNREADABLE_RESULT


def _process(record: dict[str, Any]) -> bool:
    event = decode(record)
    key = worker_key(event)
    if first_delivery(record) and not store().claim(key, OWNER):
        logger.info("worker skipped an already claimed event %s", key)
        return True
    result = _dispatch(event)
    if isinstance(result, dict) and result.get(OK_KEY) is True:
        return True
    logger.error("runtime rejected %s: %s", key, _reason(result))
    return False


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
            accepted = _process(record)
        except Exception:
            logger.exception("worker failed on message %s", identifier or "<unidentified>")
            accepted = False
        if not accepted and identifier:
            failures.append({ITEM_IDENTIFIER_KEY: identifier})
    return {BATCH_FAILURES_KEY: failures}
