import json
from collections.abc import Iterable

from pydantic import ValidationError

from repaso.schemas.telemetry import TraceEvent
from repaso.tools.call_cost import cost_or_none
from repaso.tools.call_ledger import CallOrigin, CallOutcome, CallRecord
from repaso.tools.model_usage import CallUsage

LLM_KIND = "llm"
DENIED_CALL = "denied"
FAILED_STATUS = "failed"
USAGE_AVAILABLE = "usage_available"
TRUE = "True"
USAGE_FIELDS = (
    ("input_tokens", "input_tokens"),
    ("output_tokens", "output_tokens"),
    ("cache_read_tokens", "cache_read_tokens"),
    ("cache_write_tokens", "cache_write_tokens"),
    ("reasoning_tokens", "reasoning_tokens"),
)


class TraceFormatError(ValueError):
    pass


def trace_events(lines: Iterable[str]) -> list[TraceEvent]:
    events: list[TraceEvent] = []
    for line in lines:
        text = line.strip()
        if not text.startswith("{"):
            continue
        try:
            parsed = json.loads(text)
        except ValueError:
            continue
        if not isinstance(parsed, dict) or "kind" not in parsed or "name" not in parsed:
            continue
        try:
            events.append(TraceEvent.model_validate(parsed))
        except ValidationError:
            continue
    return sorted(events, key=lambda event: event.at)


def _usage(extra: dict[str, str]) -> CallUsage | None:
    if extra.get(USAGE_AVAILABLE) != TRUE:
        return None
    return CallUsage(**{field: int(extra.get(key, 0)) for field, key in USAGE_FIELDS})


def _outcome(event: TraceEvent, call: str) -> CallOutcome:
    if call == DENIED_CALL:
        return CallOutcome.DENIED
    return CallOutcome.FAILED if event.status == FAILED_STATUS else CallOutcome.OK


def _split(name: str) -> tuple[str, str]:
    role, _, call = name.partition(".")
    if not role or not call:
        raise TraceFormatError(f"an llm trace must be named role.call, got {name!r}")
    return role, call


def call_record(event: TraceEvent) -> CallRecord:
    role, call = _split(event.name)
    extra = event.extra
    for required in ("call_id", "model_id", "evidence_origin"):
        if required not in extra:
            raise TraceFormatError(f"{event.name} carries no {required}")
    usage = _usage(extra)
    return CallRecord(
        call_id=extra["call_id"],
        at=event.at,
        role=role,
        model_id=extra["model_id"],
        kind=call,
        output_model=extra.get("output"),
        origin=CallOrigin(extra["evidence_origin"]),
        outcome=_outcome(event, call),
        latency_ms=event.duration_ms or 0.0,
        usage=usage,
        cost=None if usage is None else cost_or_none(extra["model_id"], usage),
        stop_reason=extra.get("stop_reason"),
        prompt_version=extra.get("prompt_version"),
        error=event.error or "",
    )


def call_records(events: Iterable[TraceEvent]) -> list[CallRecord]:
    return [call_record(event) for event in events if event.kind == LLM_KIND]


def hops(events: Iterable[TraceEvent]) -> list[TraceEvent]:
    return [event for event in events if event.kind != LLM_KIND]
