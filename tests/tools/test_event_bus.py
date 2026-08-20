from datetime import UTC, datetime

import pytest

from repaso.config.settings import Settings
from repaso.schemas.events import DomainEvent, EventKind
from repaso.tools.event_bus import (
    EVENTS_FILE,
    EventPublisher,
    LocalEventBus,
    build_event_publisher,
)

OCCURRED_AT = datetime(2026, 9, 1, 7, 30, tzinfo=UTC)


def make_event(
    kind: EventKind = EventKind.CHANNEL_MESSAGE, key: str = "evt-1", **payload
) -> DomainEvent:
    return DomainEvent(
        kind=kind,
        family_id="fam-1",
        idempotency_key=key,
        occurred_at=OCCURRED_AT,
        payload=payload,
    )


def make_bus(settings: Settings) -> LocalEventBus:
    return LocalEventBus(settings.local_data_dir / EVENTS_FILE)


def test_publish_appends_a_replayable_line_per_event(settings):
    bus = make_bus(settings)
    first = make_event(key="evt-1", text="hola")
    second = make_event(kind=EventKind.DAILY_CLOSE, key="evt-2")
    bus.publish(first)
    bus.publish(second)
    lines = (settings.local_data_dir / EVENTS_FILE).read_text(encoding="utf-8").splitlines()
    assert [DomainEvent.model_validate_json(line) for line in lines] == [first, second]


def test_publish_creates_the_data_directory(settings):
    assert not settings.local_data_dir.exists()
    bus = make_bus(settings)
    bus.publish(make_event())
    assert bus.path.exists()


def test_replay_reads_back_what_a_previous_bus_published(settings):
    event = make_event(text="hola")
    make_bus(settings).publish(event)
    assert make_bus(settings).replay() == [event]


def test_published_keeps_events_in_memory_for_assertions(settings):
    bus = make_bus(settings)
    first = make_event(key="evt-1")
    second = make_event(key="evt-2")
    bus.publish(first)
    bus.publish(second)
    assert bus.published == [first, second]


def test_handlers_fire_only_for_their_own_kind(settings):
    bus = make_bus(settings)
    messages: list[DomainEvent] = []
    closes: list[DomainEvent] = []
    bus.subscribe(EventKind.CHANNEL_MESSAGE, messages.append)
    bus.subscribe(EventKind.DAILY_CLOSE, closes.append)
    event = make_event(kind=EventKind.CHANNEL_MESSAGE)
    bus.publish(event)
    assert messages == [event]
    assert closes == []


def test_every_handler_of_a_kind_runs_in_subscription_order(settings):
    bus = make_bus(settings)
    calls: list[str] = []
    bus.subscribe(EventKind.DAILY_CLOSE, lambda event: calls.append("first"))
    bus.subscribe(EventKind.DAILY_CLOSE, lambda event: calls.append("second"))
    bus.publish(make_event(kind=EventKind.DAILY_CLOSE))
    assert calls == ["first", "second"]


def test_publish_without_subscribers_is_a_no_op(settings):
    bus = make_bus(settings)
    bus.subscribe(EventKind.DAILY_CLOSE, lambda event: None)
    bus.publish(make_event(kind=EventKind.MATERIAL_UPLOADED))
    assert len(bus.published) == 1


def test_a_failing_handler_does_not_stop_the_next_one(settings):
    bus = make_bus(settings)
    survived: list[DomainEvent] = []

    def explode(event: DomainEvent) -> None:
        raise RuntimeError("handler down")

    bus.subscribe(EventKind.RESPONSE_RECEIVED, explode)
    bus.subscribe(EventKind.RESPONSE_RECEIVED, survived.append)
    event = make_event(kind=EventKind.RESPONSE_RECEIVED)
    with pytest.raises(ExceptionGroup) as caught:
        bus.publish(event)
    assert [type(error) for error in caught.value.exceptions] == [RuntimeError]
    assert survived == [event]


def test_a_failing_handler_still_leaves_the_event_recorded(settings):
    bus = make_bus(settings)

    def explode(event: DomainEvent) -> None:
        raise ValueError("bad payload")

    bus.subscribe(EventKind.ESCALATION_RESOLVED, explode)
    event = make_event(kind=EventKind.ESCALATION_RESOLVED)
    with pytest.raises(ExceptionGroup):
        bus.publish(event)
    assert bus.published == [event]
    assert bus.replay() == [event]


def make_failing_handler(label: str):
    def handler(event: DomainEvent) -> None:
        raise RuntimeError(label)

    return handler


def test_every_failing_handler_is_collected_into_the_group(settings):
    bus = make_bus(settings)
    for index in range(3):
        bus.subscribe(EventKind.DAILY_SESSION_DUE, make_failing_handler(str(index)))
    with pytest.raises(ExceptionGroup) as caught:
        bus.publish(make_event(kind=EventKind.DAILY_SESSION_DUE))
    assert [str(error) for error in caught.value.exceptions] == ["0", "1", "2"]


def test_factory_returns_the_local_bus_in_local_mode(settings):
    publisher = build_event_publisher(settings)
    assert isinstance(publisher, LocalEventBus)
    assert publisher.path == settings.local_data_dir / EVENTS_FILE


def test_factory_bus_writes_under_the_configured_data_dir(tmp_path):
    settings = Settings(local_mode=True, local_data_dir=tmp_path / "local_data")
    publisher = build_event_publisher(settings)
    publisher.publish(make_event())
    assert (tmp_path / "local_data" / EVENTS_FILE).exists()


def test_local_bus_satisfies_the_publisher_protocol_without_inheriting_it(settings):
    assert isinstance(build_event_publisher(settings), EventPublisher)
    assert EventPublisher not in LocalEventBus.__mro__
