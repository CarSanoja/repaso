from datetime import UTC, datetime, timedelta
from decimal import Decimal

from repaso.core.harness.retention import (
    ANSWER_RETENTION_DAYS,
    expired,
    expiry_of,
    expiry_stamp,
)
from repaso.schemas.operation import OperationRecord

NOW = datetime(2026, 9, 1, 19, 0, tzinfo=UTC)


def record(**payload) -> OperationRecord:
    return OperationRecord(scope="f1", key="answer#chat:1", payload=payload)


def test_the_horizon_is_the_seven_days_the_consent_names():
    assert ANSWER_RETENTION_DAYS == 7
    assert expiry_stamp(NOW) == int((NOW + timedelta(days=7)).timestamp())


def test_a_record_expires_the_moment_its_stamp_is_reached():
    stamped = record(expires_at=expiry_stamp(NOW))
    assert expired(stamped, NOW) is False
    assert expired(stamped, NOW + timedelta(days=ANSWER_RETENTION_DAYS) - timedelta(1)) is False
    assert expired(stamped, NOW + timedelta(days=ANSWER_RETENTION_DAYS)) is True
    assert expired(stamped, NOW + timedelta(days=8)) is True


def test_a_record_written_before_the_horizon_existed_never_expires():
    assert expired(record(student_id="s1"), NOW + timedelta(days=3650)) is False


def test_the_stamp_survives_the_decimal_dynamodb_reads_it_back_as():
    assert expiry_of({"expires_at": Decimal(expiry_stamp(NOW))}) == float(expiry_stamp(NOW))
    assert expired(record(expires_at=Decimal(expiry_stamp(NOW))), NOW + timedelta(days=8)) is True


def test_a_non_numeric_horizon_is_not_a_horizon():
    assert expiry_of({"expires_at": "2026-09-08T19:00:00+00:00"}) is None
    assert expiry_of({"expires_at": True}) is None
    assert expiry_of({}) is None
