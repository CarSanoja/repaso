from datetime import UTC, datetime

from repaso.core.harness.clock import SimClock
from repaso.core.harness.pause import is_paused, trace_paused
from repaso.core.telemetry.sink import LocalTelemetrySink
from repaso.schemas.channel import ChannelKind
from repaso.schemas.family import Family, FamilyStatus

START = datetime(2026, 9, 1, 19, 0, tzinfo=UTC)


def make_family(status: FamilyStatus) -> Family:
    return Family(
        id="f1",
        channel=ChannelKind.TELEGRAM,
        chat_ref="100",
        invite_code="PILOT1",
        status=status,
        created_at=START,
    )


def test_only_a_paused_family_is_paused():
    assert is_paused(make_family(FamilyStatus.PAUSED)) is True
    for status in (FamilyStatus.ACTIVE, FamilyStatus.ENROLLING, FamilyStatus.FORGOTTEN):
        assert is_paused(make_family(status)) is False


def test_a_skip_names_the_family_the_student_and_the_step(tmp_path):
    sink = LocalTelemetrySink(tmp_path / "telemetry.jsonl", SimClock(START))

    trace_paused(sink, make_family(FamilyStatus.PAUSED), "daily_session", "s1")

    event = sink.events[0]
    assert (event.kind, event.name, event.status) == ("family", "paused", "skipped")
    assert event.family_id == "f1"
    assert event.student_id == "s1"
    assert event.extra["step"] == "daily_session"
