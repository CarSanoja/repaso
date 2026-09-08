import time
from collections.abc import AsyncGenerator
from typing import Any, TypeVar

from pydantic import BaseModel
from strands.models.model import Model
from strands.types.content import Messages

from repaso.config.models import ModelRole
from repaso.tools.cassette import STREAM_KIND, STRUCTURED_KIND
from repaso.tools.model_limits import ModelLimitReached
from repaso.tools.recording_model import reported_usage

T = TypeVar("T", bound=BaseModel)


class InstrumentedModel(Model):
    def __init__(self, inner: Model, role: str, telemetry: Any, limits=None) -> None:
        self.inner = inner
        self._role = role
        self._telemetry = telemetry
        self._limits = limits

    def update_config(self, **model_config: Any) -> None:
        self.inner.update_config(**model_config)

    def get_config(self) -> Any:
        return self.inner.get_config()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def _trace(self, call: str, status: str, started: float, **extra: str) -> None:
        duration = (time.perf_counter() - started) * 1000
        self._telemetry.trace(
            "llm", f"{self._role}.{call}", status=status, duration_ms=duration, **extra
        )

    async def stream(self, messages: Messages, *args: Any, **kwargs: Any):
        started = time.perf_counter()
        usage = None
        if self._limits:
            try:
                self._limits.before(self._role)
            except ModelLimitReached:
                self._trace("denied", "failed", started)
                raise
        try:
            async for event in self.inner.stream(messages, *args, **kwargs):
                usage = reported_usage(event) or usage
                yield event
        except Exception as error:
            if self._limits:
                self._limits.after(self._role, False)
            self._trace(
                STREAM_KIND,
                "failed",
                started,
                error=type(error).__name__,
                **self._usage_fields(usage),
            )
            _raise_unavailable(error)
            raise
        if self._limits:
            self._limits.after(self._role, True)
        self._trace(STREAM_KIND, "ok", started, **self._usage_fields(usage))

    def _usage_fields(self, usage):
        model_id = self.inner.get_config().get("model_id", "unknown")
        origin = getattr(self.inner, "evidence_origin", None)
        if origin is None:
            origin = "live" if type(self.inner).__name__ == "BedrockModel" else "simulation"
        fields = {
            "model_id": model_id,
            "usage_available": str(usage is not None),
            "evidence_origin": str(origin),
        }
        if usage is not None:
            fields.update(
                input_tokens=str(usage.input_tokens), output_tokens=str(usage.output_tokens)
            )
            from repaso.config.pricing import UnpricedModel, estimate_cost_usd

            try:
                fields["estimated_usd"] = str(
                    estimate_cost_usd(model_id, usage.input_tokens, usage.output_tokens)
                )
            except UnpricedModel:
                fields["cost_status"] = "unpriced"
        return fields

    async def structured_output(
        self,
        output_model: type[T],
        prompt: Messages,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict[str, T | Any], None]:
        started = time.perf_counter()
        usage = None
        if self._limits:
            try:
                self._limits.before(self._role)
            except ModelLimitReached:
                self._trace("denied", "failed", started)
                raise
        try:
            async for event in self.inner.structured_output(
                output_model, prompt, system_prompt=system_prompt, **kwargs
            ):
                usage = reported_usage(event) or usage
                yield event
        except Exception as error:
            if self._limits:
                self._limits.after(self._role, False)
            self._trace(
                STRUCTURED_KIND,
                "failed",
                started,
                error=type(error).__name__,
                output=output_model.__name__,
                **self._usage_fields(usage),
            )
            _raise_unavailable(error)
            raise
        if self._limits:
            self._limits.after(self._role, True)
        self._trace(
            STRUCTURED_KIND,
            "ok",
            started,
            output=output_model.__name__,
            **self._usage_fields(usage),
        )


def instrument_models(
    models: dict[ModelRole, Model], telemetry: Any, limits=None
) -> dict[ModelRole, Model]:
    return {
        role: InstrumentedModel(model, role.value, telemetry, limits)
        for role, model in models.items()
    }


def _raise_unavailable(error):
    code = getattr(error, "response", {}).get("Error", {}).get("Code", "")
    if isinstance(error, (TimeoutError, ConnectionError)) or code in {
        "ThrottlingException",
        "ServiceUnavailableException",
        "ModelTimeoutException",
        "InternalServerException",
        "ModelNotReadyException",
        "TooManyRequestsException",
    }:
        raise ModelLimitReached("model unavailable; pending work is preserved") from error
