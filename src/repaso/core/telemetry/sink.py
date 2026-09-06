import logging
import threading
from pathlib import Path
from typing import Protocol, runtime_checkable

from repaso.config.settings import Settings
from repaso.core.harness.clock import Clock, SystemClock
from repaso.core.telemetry.context import invocation_context
from repaso.schemas.telemetry import TraceEvent


@runtime_checkable
class TelemetrySink(Protocol):
    def emit(self, event: TraceEvent) -> None: ...

    def trace(
        self,
        kind: str,
        name: str,
        status: str = "ok",
        duration_ms: float | None = None,
        family_id: str | None = None,
        student_id: str | None = None,
        error: str | None = None,
        **extra: str,
    ) -> None: ...


class NullTelemetrySink:
    def emit(self, event: TraceEvent) -> None:
        return None

    def trace(self, kind: str, name: str, **kwargs) -> None:
        return None


class LocalTelemetrySink:
    def __init__(self, path: Path, clock: Clock | None = None) -> None:
        self._path = path
        self._clock = clock or SystemClock()
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self.events: list[TraceEvent] = []

    def emit(self, event: TraceEvent) -> None:
        self.events.append(event)
        line = event.model_dump_json()
        with self._lock, self._path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def trace(
        self,
        kind: str,
        name: str,
        status: str = "ok",
        duration_ms: float | None = None,
        family_id: str | None = None,
        student_id: str | None = None,
        error: str | None = None,
        **extra: str,
    ) -> None:
        context = invocation_context.get() or {}
        family_id = family_id or context.get("family_id")
        extra = {**context, **extra}
        extra.pop("family_id", None)
        self.emit(
            TraceEvent(
                at=self._clock.now(),
                kind=kind,
                name=name,
                status=status,
                duration_ms=duration_ms,
                family_id=family_id,
                student_id=student_id,
                error=error,
                extra={key: str(value) for key, value in extra.items()},
            )
        )


class CloudWatchTelemetrySink:
    def __init__(self, namespace: str, local_mirror: LocalTelemetrySink) -> None:
        logging.getLogger("repaso.telemetry").setLevel(logging.INFO)
        self._namespace = namespace
        self._mirror = local_mirror

    def emit(self, event: TraceEvent) -> None:
        # Logs are durable in the runtime log group. Omit child/chat identifiers
        # and exception messages; request bodies never belong in operational logs.
        logged = event.model_dump(mode="json")
        logged.pop("family_id", None)
        logged.pop("student_id", None)
        logged["error"] = event.error.split(":", 1)[0] if event.error else None
        logged["extra"] = {
            k: v for k, v in event.extra.items() if k not in ("chat_ref", "student_id", "family_id")
        }
        self._mirror.emit(TraceEvent.model_validate(logged))
        import json

        logging.getLogger("repaso.telemetry").info(json.dumps(logged))
        import boto3

        client = boto3.client("cloudwatch")
        metrics = [
            {
                "MetricName": f"{event.kind}.{event.name}.{event.status}",
                "Value": 1.0,
                "Unit": "Count",
            }
        ]
        if event.duration_ms is not None:
            metrics.append(
                {
                    "MetricName": f"{event.kind}.{event.name}.latency",
                    "Value": event.duration_ms,
                    "Unit": "Milliseconds",
                }
            )
        for key in ("input_tokens", "output_tokens", "estimated_usd"):
            if key in event.extra:
                metrics.append(
                    {"MetricName": f"llm.{key}", "Value": float(event.extra[key]), "Unit": "Count"}
                )
        try:
            client.put_metric_data(
                Namespace=self._namespace,
                MetricData=metrics,
            )
        except Exception:
            logging.getLogger("repaso.telemetry").warning("metric publication failed")

    def trace(self, kind: str, name: str, **kwargs) -> None:
        context = invocation_context.get() or {}
        fields = {
            k: kwargs.pop(k)
            for k in list(kwargs)
            if k in ("status", "duration_ms", "family_id", "student_id", "error")
        }
        fields.setdefault("family_id", context.get("family_id"))
        extra = {**context, **kwargs}
        extra.pop("family_id", None)
        self.emit(
            TraceEvent(
                at=self._mirror._clock.now(),
                kind=kind,
                name=name,
                extra={k: str(v) for k, v in extra.items()},
                **fields,
            )
        )


def build_telemetry_sink(settings: Settings, clock: Clock | None = None) -> TelemetrySink:
    local = LocalTelemetrySink(settings.local_data_dir / "telemetry.jsonl", clock)
    if settings.local_mode:
        return local
    return CloudWatchTelemetrySink("repaso", local)
