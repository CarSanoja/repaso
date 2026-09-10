from collections.abc import AsyncGenerator
from typing import Any, TypeVar

from pydantic import BaseModel
from strands.models.model import Model
from strands.types.content import Messages

from repaso.config.models import ModelRole
from repaso.tools.call_ledger import CallLedger, CallOutcome, NullCallLedger
from repaso.tools.call_watch import CallWatch
from repaso.tools.cassette import STREAM_KIND, STRUCTURED_KIND
from repaso.tools.model_limits import ModelLimitReached, transient

T = TypeVar("T", bound=BaseModel)

DENIED_CALL = "denied"


class InstrumentedModel(Model):
    def __init__(
        self,
        inner: Model,
        role: str,
        telemetry: Any,
        limits=None,
        ledger: CallLedger | None = None,
        clock=None,
    ) -> None:
        self.inner = inner
        self._role = role
        self._telemetry = telemetry
        self._limits = limits
        self._ledger = ledger or NullCallLedger()
        self._clock = clock

    def update_config(self, **model_config: Any) -> None:
        self.inner.update_config(**model_config)

    def get_config(self) -> Any:
        return self.inner.get_config()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def _watch(self, kind: str, output_model: str | None = None) -> CallWatch:
        return CallWatch(self.inner, self._role, kind, output_model, self._clock)

    def _admit(self, watch: CallWatch) -> None:
        if not self._limits:
            return
        try:
            self._limits.before(self._role)
        except ModelLimitReached as denial:
            self._close(watch, CallOutcome.DENIED, type(denial).__name__, DENIED_CALL)
            raise

    def _close(
        self, watch: CallWatch, outcome: CallOutcome, error: str = "", call: str | None = None
    ) -> None:
        watch.close()
        extra = watch.trace_fields() if call is None else {}
        if error:
            extra["error"] = error
        self._telemetry.trace(
            "llm",
            f"{self._role}.{call or watch.kind}",
            status="ok" if outcome is CallOutcome.OK else "failed",
            duration_ms=watch.latency_ms,
            **extra,
        )
        self._ledger.append(watch.record(outcome, error))

    async def stream(self, messages: Messages, *args: Any, **kwargs: Any):
        watch = self._watch(STREAM_KIND)
        self._admit(watch)
        try:
            async for event in self.inner.stream(messages, *args, **kwargs):
                watch.observe(event)
                yield event
        except Exception as error:
            if self._limits:
                self._limits.after(self._role, False)
            self._close(watch, CallOutcome.FAILED, type(error).__name__)
            _raise_unavailable(error)
            raise
        if self._limits:
            self._limits.after(self._role, True)
        self._close(watch, CallOutcome.OK)

    async def structured_output(
        self,
        output_model: type[T],
        prompt: Messages,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict[str, T | Any], None]:
        watch = self._watch(STRUCTURED_KIND, output_model.__name__)
        self._admit(watch)
        try:
            async for event in self.inner.structured_output(
                output_model, prompt, system_prompt=system_prompt, **kwargs
            ):
                watch.observe(event)
                yield event
        except Exception as error:
            if self._limits:
                self._limits.after(self._role, False)
            self._close(watch, CallOutcome.FAILED, type(error).__name__)
            _raise_unavailable(error)
            raise
        if self._limits:
            self._limits.after(self._role, True)
        self._close(watch, CallOutcome.OK)


def instrument_models(
    models: dict[ModelRole, Model],
    telemetry: Any,
    limits=None,
    ledger: CallLedger | None = None,
    clock=None,
) -> dict[ModelRole, Model]:
    return {
        role: InstrumentedModel(model, role.value, telemetry, limits, ledger, clock)
        for role, model in models.items()
    }


def _raise_unavailable(error):
    if transient(error):
        raise ModelLimitReached("model unavailable; pending work is preserved") from error
