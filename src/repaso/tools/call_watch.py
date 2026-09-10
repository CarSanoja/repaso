import time
from typing import Any

from repaso.core.harness.clock import Clock, SystemClock
from repaso.tools.call_cost import CallCost, cost_or_none
from repaso.tools.call_ledger import (
    CallOrigin,
    CallOutcome,
    CallRecord,
    declared_prompt_version,
    new_call_id,
)
from repaso.tools.model_usage import CallUsage, stop_reason_from_event, usage_from_event

UNKNOWN_MODEL = "unknown"
LIVE_MODEL_TYPE = "BedrockModel"
REPLAY_MODEL_TYPE = "CassetteModel"


def call_origin(model: Any) -> CallOrigin:
    declared = getattr(model, "evidence_origin", None)
    if declared in set(CallOrigin):
        return CallOrigin(declared)
    kind = type(model).__name__
    if kind == LIVE_MODEL_TYPE:
        return CallOrigin.LIVE
    if kind == REPLAY_MODEL_TYPE:
        return CallOrigin.REPLAYED
    return CallOrigin.SIMULATED


def model_id_of(model: Any) -> str:
    config = model.get_config()
    model_id = config.get("model_id") if isinstance(config, dict) else None
    return model_id if isinstance(model_id, str) and model_id else UNKNOWN_MODEL


class CallWatch:
    def __init__(
        self,
        inner: Any,
        role: str,
        kind: str,
        output_model: str | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.call_id = new_call_id()
        self.role = role
        self.kind = kind
        self.output_model = output_model
        self.model_id = model_id_of(inner)
        self.origin = call_origin(inner)
        self.usage: CallUsage | None = None
        self.stop_reason: str | None = None
        self.latency_ms = 0.0
        self._clock = clock or SystemClock()
        self._started = time.perf_counter()

    def observe(self, event: Any) -> None:
        self.usage = usage_from_event(event) or self.usage
        self.stop_reason = stop_reason_from_event(event) or self.stop_reason

    def close(self) -> float:
        self.latency_ms = (time.perf_counter() - self._started) * 1000
        return self.latency_ms

    def trace_fields(self) -> dict[str, str]:
        fields = {
            "call_id": self.call_id,
            "model_id": self.model_id,
            "usage_available": str(self.usage is not None),
            "evidence_origin": self.origin.value,
        }
        if self.output_model is not None:
            fields["output"] = self.output_model
        if self.usage is None:
            return fields
        fields["input_tokens"] = str(self.usage.input_tokens)
        fields["output_tokens"] = str(self.usage.output_tokens)
        for name, tokens in (
            ("cache_read_tokens", self.usage.cache_read_tokens),
            ("cache_write_tokens", self.usage.cache_write_tokens),
            ("reasoning_tokens", self.usage.reasoning_tokens),
        ):
            if tokens:
                fields[name] = str(tokens)
        cost = self.cost()
        if cost is None:
            fields["cost_status"] = "unpriced"
        else:
            fields["estimated_usd"] = str(cost.total_usd)
        return fields

    def cost(self) -> CallCost | None:
        return None if self.usage is None else cost_or_none(self.model_id, self.usage)

    def record(self, outcome: CallOutcome, error: str = "") -> CallRecord:
        return CallRecord(
            call_id=self.call_id,
            at=self._clock.now(),
            role=self.role,
            model_id=self.model_id,
            kind=self.kind,
            output_model=self.output_model,
            origin=self.origin,
            outcome=outcome,
            latency_ms=self.latency_ms,
            usage=self.usage,
            cost=self.cost(),
            stop_reason=self.stop_reason,
            prompt_version=declared_prompt_version(),
            error=error,
        )
