import json
import logging
from hmac import compare_digest
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from repaso.api.dependencies import AppContainer
from repaso.channel.telegram.parser import parse_update, update_id_of
from repaso.schemas.channel import InboundMessage
from repaso.schemas.events import DomainEvent, EventKind
from repaso.schemas.operation import OperationRecord

SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"

logger = logging.getLogger(__name__)
router = APIRouter()


def _channel_event(message: InboundMessage) -> DomainEvent:
    return DomainEvent(
        kind=EventKind.CHANNEL_MESSAGE,
        family_id=None,
        idempotency_key=f"{message.chat_ref}#{message.message_ref}",
        occurred_at=message.received_at,
        payload=message.model_dump(mode="json"),
    )


def _authorize(container: AppContainer, provided: str | None) -> None:
    if not container.telegram_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="secret_not_configured"
        )
    if not provided or not compare_digest(provided, container.telegram_secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_secret")


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request) -> dict[str, Any]:
    container: AppContainer = request.app.state.container
    _authorize(container, request.headers.get(SECRET_HEADER))
    try:
        update = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("telegram webhook ignored malformed JSON")
        return {"ok": True, "error": "logged"}
    try:
        message = parse_update(update, now=container.clock.now() if container.clock else None)
        if message is None:
            return {"ok": True, "ignored": True}
        scope = f"chat:{message.chat_ref}"
        key = f"published#{update_id_of(update) or message.message_ref}"
        if container.store.get_record(scope, key):
            return {"ok": True, "duplicate": True}
        container.publisher.publish(_channel_event(message))
        container.store.put_record(OperationRecord(scope=scope, key=key, payload={"ok": True}))
    except Exception:
        logger.exception("telegram webhook processing failed")
        raise HTTPException(status_code=503, detail="delivery_pending") from None
    return {"ok": True}
