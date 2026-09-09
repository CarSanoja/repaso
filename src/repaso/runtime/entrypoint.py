import asyncio
import logging
import time
from hashlib import sha256
from typing import Any
from uuid import uuid4

from repaso.core.orchestration.context import Services
from repaso.core.telemetry.context import invocation_context
from repaso.runtime.context import runtime_services
from repaso.runtime.errors import ErrorCode, InvocationError
from repaso.runtime.handlers import HANDLERS
from repaso.runtime.payload import parse_request
from repaso.runtime.results import error_result, kind_hint, ok_result
from repaso.schemas.events import EventKind
from repaso.schemas.operation import OperationRecord
from repaso.tools.model_limits import MESSAGE_SCOPE_KEY, ModelLimitReached

logger = logging.getLogger(__name__)

LOOP_MESSAGE = "invoke() cannot run inside a running event loop; await invoke_async() instead"
COHORT_WIDE_KINDS = frozenset({EventKind.DAILY_CLOSE})


def supported_kinds() -> list[str]:
    return sorted(kind.value for kind in HANDLERS)


def _message_bound(kind: EventKind, correlation: str) -> dict[str, str]:
    if kind in COHORT_WIDE_KINDS:
        return {}
    return {MESSAGE_SCOPE_KEY: correlation}


async def invoke_async(payload: dict[str, Any], services: Services | None = None) -> dict[str, Any]:
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
        scope = request.family_id or "system"
        family = context.store.get_family(request.family_id) if request.family_id else None
        cache_scope = scope
        lease_scopes = [scope]
        if kind == "channel_message":
            chat = str(request.payload.get("chat_ref", ""))
            family = context.store.find_family_by_chat(
                str(request.payload.get("channel", "telegram")), chat
            )
            scope = family.id if family else f"chat:{chat}"
            cache_scope = f"chat:{chat}"
            lease_scopes = list(dict.fromkeys([cache_scope, scope]))
        key = f"invocation#{kind}#{request.idempotency_key}" if request.idempotency_key else None
        owner = uuid4().hex
        acquired = []
        for lease in lease_scopes:
            if not context.store.acquire_lease(lease, owner, time.time() + 1200):
                for held in acquired:
                    context.store.release_lease(held, owner)
                raise RuntimeError("family operation in progress; retry required")
            acquired.append(lease)
        correlation = sha256((key or owner).encode()).hexdigest()[:24]
        token = invocation_context.set(
            {
                "family_id": scope,
                "timezone": family.timezone
                if family
                else ("America/Caracas" if kind == "daily_close" else "UTC"),
                "correlation_id": correlation,
                **_message_bound(request.kind, correlation),
            }
        )
        try:
            cached = context.store.get_record(cache_scope, key) if key else None
            pending_key = f"pending#{key}" if key and kind != "daily_close" else None
            if cached:
                if pending_key:
                    context.store.put_record(
                        OperationRecord(scope=scope, key=pending_key, payload={"state": "complete"})
                    )
                return cached.payload["result"]
            if pending_key and request.payload.get("callback_data") != "forget:yes":
                if not context.store.get_record(scope, pending_key):
                    context.store.put_record(
                        OperationRecord(
                            scope=scope,
                            key=pending_key,
                            payload={
                                "state": "pending",
                                "request": request.model_dump(mode="json"),
                                "created_at": context.clock.now().isoformat(),
                            },
                        )
                    )
            try:
                result = await handler(context, request)
            except ModelLimitReached:
                _notify_waiting(context, request, scope)
                raise
            response = ok_result(kind, result)
            forgotten = request.payload.get("callback_data") == "forget:yes"
            if key and not forgotten:
                context.store.put_record(
                    OperationRecord(scope=cache_scope, key=key, payload={"result": response})
                )
                if pending_key:
                    context.store.put_record(
                        OperationRecord(scope=scope, key=pending_key, payload={"state": "complete"})
                    )
        finally:
            invocation_context.reset(token)
            for held in acquired:
                context.store.release_lease(held, owner)
    except InvocationError as error:
        return error_result(error.code, error.message, kind)
    except Exception as error:
        logger.error("runtime invocation failed kind=%s type=%s", kind, type(error).__name__)
        return error_result(ErrorCode.HANDLER_FAILED, f"{type(error).__name__}: {error}", kind)
    return ok_result(kind, result)


def invoke(payload: dict[str, Any], services: Services | None = None) -> dict[str, Any]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(invoke_async(payload, services))
    return error_result(ErrorCode.EVENT_LOOP_RUNNING, LOOP_MESSAGE, kind_hint(payload))


def _notify_waiting(services, request, scope):
    from repaso.core.orchestration.outbox import deliver
    from repaso.i18n import msg
    from repaso.schemas.channel import ChannelKind, OutboundMessage
    from repaso.schemas.common import Lang

    family = services.store.get_family(scope)
    chat = family.chat_ref if family else request.payload.get("chat_ref")
    if not chat:
        return
    message = OutboundMessage(
        channel=family.channel if family else ChannelKind.TELEGRAM,
        chat_ref=str(chat),
        text=msg("model_waiting", family.lang if family else Lang.ES),
    )
    deliver(services, [message], f"model-waiting#{services.clock.today()}", scope)
