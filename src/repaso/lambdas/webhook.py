import json
import logging
from typing import Any

ACK_BODY = json.dumps({"ok": True})
ACK_HEADERS = {"content-type": "application/json"}
SERVER_ERROR_FLOOR = 500
STATUS_KEY = "statusCode"

logger = logging.getLogger(__name__)

_ADAPTER: Any = None


def ack() -> dict[str, Any]:
    return {
        STATUS_KEY: 200,
        "headers": dict(ACK_HEADERS),
        "body": ACK_BODY,
        "isBase64Encoded": False,
    }


def build_adapter() -> Any:
    from mangum import Mangum

    from repaso.api.main import create_app
    from repaso.lambdas.bootstrap import container

    return Mangum(create_app(container()), lifespan="off")


def adapter() -> Any:
    global _ADAPTER
    if _ADAPTER is None:
        _ADAPTER = build_adapter()
    return _ADAPTER


def reset_adapter() -> None:
    global _ADAPTER
    _ADAPTER = None


def _downgraded(response: Any) -> dict[str, Any]:
    if not isinstance(response, dict):
        logger.error("telegram webhook produced a response that is not a lambda payload")
        return ack()
    try:
        code = int(response.get(STATUS_KEY, 200))
    except (TypeError, ValueError):
        logger.error("telegram webhook produced an unreadable status")
        return ack()
    if code >= SERVER_ERROR_FLOOR:
        logger.error("telegram webhook downgraded status %s to an ack", code)
        return ack()
    return response


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    try:
        response = adapter()(event, context)
    except Exception:
        logger.exception("telegram webhook invocation failed")
        return ack()
    return _downgraded(response)
