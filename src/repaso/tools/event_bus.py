from collections.abc import Callable
from pathlib import Path
from typing import Protocol, runtime_checkable

from repaso.config.settings import Settings
from repaso.schemas.events import DomainEvent, EventKind

EVENT_SOURCE = "repaso"
EVENTS_FILE = "events.jsonl"

EventHandler = Callable[[DomainEvent], None]


@runtime_checkable
class EventPublisher(Protocol):
    def publish(self, event: DomainEvent) -> None: ...


class LocalEventBus:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._handlers: dict[EventKind, list[EventHandler]] = {}
        self.published: list[DomainEvent] = []

    @property
    def path(self) -> Path:
        return self._path

    def subscribe(self, kind: EventKind, handler: EventHandler) -> None:
        self._handlers.setdefault(kind, []).append(handler)

    def publish(self, event: DomainEvent) -> None:
        self._append(event)
        self.published.append(event)
        self._dispatch(event)

    def replay(self) -> list[DomainEvent]:
        if not self._path.exists():
            return []
        return [
            DomainEvent.model_validate_json(line)
            for line in self._path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _append(self, event: DomainEvent) -> None:
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(event.model_dump_json() + "\n")

    def _dispatch(self, event: DomainEvent) -> None:
        failures: list[Exception] = []
        for handler in list(self._handlers.get(event.kind, ())):
            try:
                handler(event)
            except Exception as error:
                failures.append(error)
        if failures:
            raise ExceptionGroup(f"handlers failed for {event.kind.value}", failures)


class EventBridgePublisher:
    def __init__(self, bus_name: str) -> None:
        self._bus_name = bus_name

    def publish(self, event: DomainEvent) -> None:
        from repaso.config.clients import events_client

        client = events_client()
        client.put_events(
            Entries=[
                {
                    "EventBusName": self._bus_name,
                    "Source": EVENT_SOURCE,
                    "DetailType": event.kind.value,
                    "Detail": event.model_dump_json(),
                }
            ]
        )


def build_event_publisher(settings: Settings) -> EventPublisher:
    if settings.local_mode:
        return LocalEventBus(settings.local_data_dir / EVENTS_FILE)
    return EventBridgePublisher(settings.event_bus)
