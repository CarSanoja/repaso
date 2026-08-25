import threading
from pathlib import Path
from typing import Protocol, runtime_checkable

from repaso.config.settings import Settings
from repaso.core.harness.clock import Clock, SystemClock
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
        self._namespace = namespace
        self._mirror = local_mirror

    def emit(self, event: TraceEvent) -> None:
        self._mirror.emit(event)
        import boto3

        client = boto3.client("cloudwatch")
        client.put_metric_data(
            Namespace=self._namespace,
            MetricData=[
                {
                    "MetricName": f"{event.kind}.{event.status}",
                    "Value": event.duration_ms or 1.0,
                    "Unit": "Milliseconds" if event.duration_ms else "Count",
                }
            ],
        )

    def trace(self, kind: str, name: str, **kwargs) -> None:
        self._mirror.trace(kind, name, **kwargs)


def build_telemetry_sink(settings: Settings, clock: Clock | None = None) -> TelemetrySink:
    local = LocalTelemetrySink(settings.local_data_dir / "telemetry.jsonl", clock)
    if settings.local_mode:
        return local
    return CloudWatchTelemetrySink("repaso", local)
