import asyncio
import logging
from typing import Any

from repaso.core.orchestration.context import Services
from repaso.runtime.context import runtime_services
from repaso.runtime.errors import ErrorCode, InvocationError
from repaso.runtime.handlers import HANDLERS
from repaso.runtime.payload import parse_request
from repaso.runtime.results import error_result, kind_hint, ok_result

logger = logging.getLogger(__name__)

LOOP_MESSAGE = "invoke() cannot run inside a running event loop; await invoke_async() instead"


def supported_kinds() -> list[str]:
    return sorted(kind.value for kind in HANDLERS)


async def invoke_async(
    payload: dict[str, Any], services: Services | None = None
) -> dict[str, Any]:
    try:
        request = parse_request(payload)
    except InvocationError as error:
        return error_result(error.code, error.message, kind_hint(payload))
    kind = request.kind.value
    handler = HANDLERS.get(request.kind)
    if handler is None:
        return error_result(
            ErrorCode.UNSUPPORTED_KIND,
            f"event kind '{kind}' has no runtime handler; supported: {supported_kinds()}",
            kind,
        )
    try:
        context = services if services is not None else runtime_services()
        result = await handler(context, request)
    except InvocationError as error:
        return error_result(error.code, error.message, kind)
    except Exception as error:
        logger.exception("runtime invocation failed for %s", kind)
        return error_result(
            ErrorCode.HANDLER_FAILED, f"{type(error).__name__}: {error}", kind
        )
    return ok_result(kind, result)


def invoke(payload: dict[str, Any], services: Services | None = None) -> dict[str, Any]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(invoke_async(payload, services))
    return error_result(ErrorCode.EVENT_LOOP_RUNNING, LOOP_MESSAGE, kind_hint(payload))
