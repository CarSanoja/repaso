from datetime import UTC, datetime, timedelta

import boto3
import pytest
from moto import mock_aws

from repaso.core.harness.clock import SimClock
from repaso.core.harness.retention import ANSWER_RETENTION_DAYS, TTL_ATTRIBUTE
from repaso.schemas.grading import EvidenceSpan, GradedBy, GradeResult
from repaso.tools.grade_log import DynamoGradeLog, LocalGradeLog
from repaso.tools.grade_words import WORDS_PREFIX, attempt_only, words_of

NOW = datetime(2026, 9, 1, 19, 0, tzinfo=UTC)
WROTE = "la mitad, porque 2/4 y 1/2 valen lo mismo"
TABLE = "repaso"


def grade(item_id: str = "i1", quote: str = WROTE, at: datetime = NOW) -> GradeResult:
    return GradeResult(
        id=f"study:{item_id}",
        student_id="s1",
        item_id=item_id,
        correct=True,
        confidence=1.0,
        graded_by=GradedBy.DETERMINISTIC,
        latency_seconds=4.0,
        evidence=EvidenceSpan(quote=quote, source_ref=f"response:s1:{item_id}"),
        feedback="",
        graded_at=at,
    )


@pytest.fixture
def cloud_log(monkeypatch):
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
            TableName=TABLE,
            BillingMode="PAY_PER_REQUEST",
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": n, "AttributeType": "S"} for n in ("pk", "sk", "gsi1pk", "gsi1sk")
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "gsi1",
                    "Projection": {"ProjectionType": "ALL"},
                    "KeySchema": [
                        {"AttributeName": "gsi1pk", "KeyType": "HASH"},
                        {"AttributeName": "gsi1sk", "KeyType": "RANGE"},
                    ],
                }
            ],
        )
        client.update_time_to_live(
            TableName=TABLE,
            TimeToLiveSpecification={"Enabled": True, "AttributeName": TTL_ATTRIBUTE},
        )
        for module in ("repaso.config.clients", "repaso.tools.state_dynamo_io"):
            monkeypatch.setattr(f"{module}.dynamodb_client", lambda: client)
        yield DynamoGradeLog(TABLE, SimClock(NOW)), client


def rows(client) -> list[dict]:
    return client.scan(TableName=TABLE)["Items"]


def test_the_attempt_carries_no_quote_and_the_words_carry_the_horizon():
    result = grade()

    assert attempt_only(result).evidence.quote == ""
    assert attempt_only(result).correct is True
    said = words_of(result)
    assert said.quote == WROTE
    assert said.expires_at == int((NOW + timedelta(days=ANSWER_RETENTION_DAYS)).timestamp())


def test_an_attempt_with_nothing_written_needs_no_words_row():
    assert words_of(grade(quote="")) is None


def test_the_local_attempt_row_holds_no_words(tmp_path):
    LocalGradeLog(tmp_path, SimClock(NOW)).append(grade())

    assert WROTE not in (tmp_path / "grades.jsonl").read_text(encoding="utf-8")
    assert WROTE in (tmp_path / "grade_words.jsonl").read_text(encoding="utf-8")


def test_the_words_are_readable_until_the_horizon(tmp_path):
    clock = SimClock(NOW)
    log = LocalGradeLog(tmp_path, clock)
    log.append(grade())

    clock.advance(days=ANSWER_RETENTION_DAYS - 1)

    assert log.by_student("s1")[0].evidence.quote == WROTE


def test_the_attempt_outlives_the_words(tmp_path):
    clock = SimClock(NOW)
    log = LocalGradeLog(tmp_path, clock)
    log.append(grade())

    clock.advance(days=ANSWER_RETENTION_DAYS)
    kept = log.by_student("s1")

    assert len(kept) == 1
    assert kept[0].evidence.quote == ""
    assert kept[0].correct is True
    assert kept[0].graded_at == NOW
    assert kept[0].latency_seconds == 4.0


def test_forgetting_a_student_takes_the_words_with_it(tmp_path):
    log = LocalGradeLog(tmp_path, SimClock(NOW))
    log.append(grade())

    log.forget_student("s1")

    assert log.by_student("s1") == []
    assert WROTE not in (tmp_path / "grade_words.jsonl").read_text(encoding="utf-8")


def test_the_cloud_writes_the_words_once_with_a_ttl(cloud_log):
    log, client = cloud_log
    log.append(grade())

    stored = rows(client)
    carrying = [row for row in stored if WROTE in str(row)]
    assert len(stored) == 3
    assert len(carrying) == 1
    assert carrying[0]["sk"]["S"].startswith(WORDS_PREFIX)
    assert int(carrying[0]["expires_at"]["N"]) == int(
        (NOW + timedelta(days=ANSWER_RETENTION_DAYS)).timestamp()
    )


def test_no_cloud_attempt_row_expires(cloud_log):
    log, client = cloud_log
    log.append(grade())

    attempts = [row for row in rows(client) if not row["sk"]["S"].startswith(WORDS_PREFIX)]
    assert len(attempts) == 2
    assert all("expires_at" not in row for row in attempts)
    assert all(WROTE not in str(row) for row in attempts)


def test_the_cloud_attempt_survives_the_row_the_table_expires(cloud_log):
    log, client = cloud_log
    log.append(grade())
    expiring = [row for row in rows(client) if row["sk"]["S"].startswith(WORDS_PREFIX)][0]

    client.delete_item(
        TableName=TABLE, Key={"pk": expiring["pk"], "sk": expiring["sk"]}
    )
    kept = log.by_student("s1")

    assert len(kept) == 1
    assert kept[0].evidence.quote == ""
    assert kept[0].correct is True


def test_the_only_row_the_table_would_sweep_is_the_one_holding_the_words(cloud_log):
    log, client = cloud_log
    log.append(grade())
    swept = client.describe_time_to_live(TableName=TABLE)["TimeToLiveDescription"]

    stamped = [row for row in rows(client) if swept["AttributeName"] in row]

    assert swept["TimeToLiveStatus"] == "ENABLED"
    assert len(stamped) == 1
    assert WROTE in str(stamped[0])


def test_the_cloud_withholds_the_words_before_the_table_gets_round_to_them(cloud_log):
    log, client = cloud_log
    log.append(grade())
    horizon = NOW + timedelta(days=ANSWER_RETENTION_DAYS)

    kept = DynamoGradeLog(TABLE, SimClock(horizon)).by_student("s1")

    assert [row for row in rows(client) if WROTE in str(row)]
    assert kept[0].evidence.quote == ""
    assert kept[0].correct is True


def test_the_cloud_reader_joins_the_words_back_while_they_live(cloud_log):
    log, _ = cloud_log
    log.append(grade())

    assert log.by_student("s1")[0].evidence.quote == WROTE
    assert log.by_item("i1")[0].evidence.quote == ""


def test_forgetting_a_student_in_the_cloud_takes_the_words(cloud_log):
    log, client = cloud_log
    log.append(grade())

    log.forget_student("s1")

    assert rows(client) == []
