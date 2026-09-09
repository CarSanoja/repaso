from datetime import UTC, datetime, timedelta

import pytest

from repaso.channel.throttle import Admission, admit, report
from repaso.core.harness.clock import SimClock
from repaso.core.telemetry.sink import LocalTelemetrySink
from repaso.schemas.channel import ChannelKind
from repaso.schemas.common import Lang
from repaso.schemas.enrollment import EnrollmentProgress, EnrollmentStep
from repaso.tools.call_quota import build_call_quota
from repaso.tools.state_store import build_state_store
from tests.orchestration.fixtures import seed_family

CHANNEL = "telegram"
STRANGER = "9001"
FAMILY_CHAT = "100"
NOW = datetime(2026, 9, 1, 19, 0, tzinfo=UTC)
PER_MINUTE = 3
PER_DAY = 4


@pytest.fixture
def gate(settings):
    tuned = settings.model_copy(
        update={
            "chat_messages_per_minute": PER_MINUTE,
            "unknown_chat_daily_messages": PER_DAY,
        }
    )
    store = build_state_store(tuned)
    quota = build_call_quota(tuned)

    def check(chat_ref: str, at: datetime = NOW) -> Admission:
        return admit(store, quota, tuned, at, CHANNEL, chat_ref)

    return check, store, quota, tuned


def enrolling(chat_ref: str) -> EnrollmentProgress:
    return EnrollmentProgress(
        channel=ChannelKind.TELEGRAM,
        chat_ref=chat_ref,
        lang=Lang.ES,
        step=EnrollmentStep.ALIAS,
        invite_code="PILOTO-1",
    )


def test_a_family_sending_at_a_human_pace_is_always_admitted(gate):
    check, store, _, _ = gate
    seed_family(store, chat_ref=FAMILY_CHAT)

    for minute in range(10):
        at = NOW + timedelta(minutes=minute)
        assert check(FAMILY_CHAT, at) is Admission.ADMITTED


def test_a_chat_over_the_minute_limit_is_refused(gate):
    check, store, _, _ = gate
    seed_family(store, chat_ref=FAMILY_CHAT)

    admitted = [check(FAMILY_CHAT) for _ in range(PER_MINUTE)]

    assert admitted == [Admission.ADMITTED] * PER_MINUTE
    assert check(FAMILY_CHAT) is Admission.RATE_LIMITED


def test_the_next_minute_gives_the_chat_its_allowance_back(gate):
    check, store, _, _ = gate
    seed_family(store, chat_ref=FAMILY_CHAT)
    for _ in range(PER_MINUTE + 2):
        check(FAMILY_CHAT)

    assert check(FAMILY_CHAT, NOW + timedelta(minutes=1)) is Admission.ADMITTED


def test_one_chat_over_the_limit_does_not_refuse_another(gate):
    check, store, _, _ = gate
    seed_family(store, chat_ref=FAMILY_CHAT)
    seed_family(store, family_id="f2", chat_ref="200")
    for _ in range(PER_MINUTE + 1):
        check(FAMILY_CHAT)

    assert check("200") is Admission.ADMITTED


def test_a_stranger_may_knock_a_bounded_number_of_times(gate):
    check, _, _, _ = gate

    admitted = [check(STRANGER, NOW + timedelta(minutes=n)) for n in range(PER_DAY)]

    assert admitted == [Admission.ADMITTED] * PER_DAY
    later = check(STRANGER, NOW + timedelta(minutes=PER_DAY))
    assert later is Admission.UNKNOWN_CHAT_EXHAUSTED


def test_the_stranger_allowance_returns_the_next_day(gate):
    check, _, _, _ = gate
    for minute in range(PER_DAY + 2):
        check(STRANGER, NOW + timedelta(minutes=minute))

    assert check(STRANGER, NOW + timedelta(days=1)) is Admission.ADMITTED


def test_a_chat_part_way_through_enrollment_is_not_a_stranger(gate):
    check, store, _, _ = gate
    store.put_enrollment(enrolling(STRANGER))

    for minute in range(PER_DAY + 3):
        assert check(STRANGER, NOW + timedelta(minutes=minute)) is Admission.ADMITTED


def test_an_enrolled_family_never_spends_the_stranger_allowance(gate):
    check, store, _, _ = gate
    seed_family(store, chat_ref=FAMILY_CHAT)

    for minute in range(PER_DAY + 3):
        assert check(FAMILY_CHAT, NOW + timedelta(minutes=minute)) is Admission.ADMITTED


def test_a_refusal_is_reported_once_a_minute_however_loud_the_chat(settings, gate):
    _, _, quota, _ = gate
    telemetry = LocalTelemetrySink(settings.local_data_dir / "traces.jsonl", SimClock(NOW))

    for _ in range(20):
        report(telemetry, quota, NOW, CHANNEL, STRANGER, Admission.RATE_LIMITED)
    report(telemetry, quota, NOW + timedelta(minutes=1), CHANNEL, STRANGER, Admission.RATE_LIMITED)

    assert [event.name for event in telemetry.events] == ["rate_limited", "rate_limited"]
    assert {event.status for event in telemetry.events} == {"refused"}
