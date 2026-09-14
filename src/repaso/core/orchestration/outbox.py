from hashlib import sha256
from uuid import uuid4

from repaso.core.telemetry.context import invocation_context
from repaso.schemas.channel import OutboundMessage
from repaso.schemas.operation import OperationRecord


def deliver(
    services, messages: list[OutboundMessage], key: str | None = None, scope: str | None = None
) -> list[str]:
    if not messages:
        return []
    family = services.store.find_family_by_chat(messages[0].channel.value, messages[0].chat_ref)
    scope = scope or (family.id if family else f"chat:{messages[0].chat_ref}")
    key = f"outbox#{key or uuid4().hex}"
    record = services.store.get_record(scope, key)
    if record is None:
        record = OperationRecord(
            scope=scope,
            key=key,
            payload={
                "created_at": services.clock.now().isoformat(),
                "messages": [m.model_dump(mode="json") for m in messages],
                "receipts": [],
                "attempts": 0,
            },
        )
        services.store.put_record(record)
    payload = record.payload
    parent = (invocation_context.get() or {}).get("correlation_id", "")
    for raw in payload["messages"][len(payload["receipts"]) :]:
        payload["attempts"] += 1
        services.store.put_record(record)
        services.telemetry.trace(
            "delivery",
            "attempted",
            family_id=scope,
            correlation_id=sha256(key.encode()).hexdigest()[:24],
            parent_correlation_id=parent,
        )
        try:
            receipt = services.sender.send(OutboundMessage.model_validate(raw))
        except Exception:
            services.telemetry.trace(
                "delivery",
                "failed",
                status="failed",
                family_id=scope,
                correlation_id=sha256(key.encode()).hexdigest()[:24],
                parent_correlation_id=parent,
            )
            raise
        payload["receipts"].append(receipt)
        services.store.put_record(record)
        services.telemetry.trace(
            "delivery",
            "acknowledged",
            family_id=scope,
            correlation_id=sha256(key.encode()).hexdigest()[:24],
            parent_correlation_id=parent,
        )
    return list(payload["receipts"])
