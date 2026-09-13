import boto3
import pytest
from moto import mock_aws

from repaso.config.models import ModelRole
from repaso.core.harness.retention import expiry_stamp
from repaso.core.orchestration.privacy import forget_family
from repaso.core.orchestration.quarantine_resolution import resolve_quarantine
from repaso.core.orchestration.runner import handle_answer, start_daily_session
from repaso.core.orchestration.study_answer import current_item
from repaso.core.orchestration.study_channel import handle_study_text
from repaso.core.orchestration.study_flow import start_sitting
from repaso.tools.grade_log import DynamoGradeLog
from repaso.tools.llm import LocalPlaybackModel
from repaso.tools.media_store import S3MediaStore
from repaso.tools.state_dynamo import DynamoStateStore
from tests.orchestration.fixtures import FRACTIONS, seed_family, seed_held_answer, seed_open_item
from tests.orchestration.test_gap_recovery import IntermittentSender, make_services, seed_mcqs
from tests.tools.moto_atomicity import OneCallAtATime


@pytest.fixture
def cloud_services(settings, monkeypatch):
    with mock_aws():
        client = OneCallAtATime(boto3.client("dynamodb", region_name="us-east-1"))
        client.create_table(
            TableName="repaso",
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
        for module in (
            "repaso.config.clients",
            "repaso.tools.state_dynamo",
            "repaso.tools.state_dynamo_io",
        ):
            monkeypatch.setattr(f"{module}.dynamodb_client", lambda: client)
        media = boto3.client("s3", region_name="us-east-1")
        media.create_bucket(Bucket="repaso-synthetic-media")
        media.put_bucket_versioning(
            Bucket="repaso-synthetic-media", VersioningConfiguration={"Status": "Enabled"}
        )
        monkeypatch.setattr("repaso.config.clients.s3_client", lambda: media)
        s = make_services(settings)
        s.store = DynamoStateStore("repaso")
        s.grade_log = DynamoGradeLog("repaso", s.clock)
        s.media = S3MediaStore("repaso-synthetic-media")
        yield s, client, media


@pytest.mark.parametrize("accepted", [True, False])
def test_cloud_human_outcome_is_atomic_and_repeatable(cloud_services, accepted):
    s, _, _ = cloud_services
    family, student = seed_family(s.store)
    seed_open_item(s.store)
    held = seed_held_answer(s.store, family.id, student.id)
    resolve_quarantine(s, family, held, accepted)
    resolve_quarantine(s, family, held, not accepted)
    assert s.store.get_mastery(student.id, FRACTIONS).attempts == 1
    assert s.store.get_mastery(student.id, FRACTIONS).correct == int(accepted)
    assert len(s.grade_log.by_student(student.id)) == 1


@pytest.mark.asyncio
async def test_cloud_delivery_recovery_and_complete_family_erasure(cloud_services):
    s, client, media = cloud_services
    family, student = seed_family(s.store)
    other, other_student = seed_family(s.store, "family-two", "200")
    seed_mcqs(s, family.id)
    s.sender = IntermittentSender(1)
    with pytest.raises(ConnectionError):
        await start_daily_session(s, family, student)
    await start_daily_session(s, family, student)
    await handle_answer(s, family, student, "1", 45, response_id="first")
    s.media.put(f"media/{family.id}/page", b"first version", "text/plain")
    s.media.put(f"media/{family.id}/page", b"second version", "text/plain")
    s.media.put(f"media/{other.id}/page", b"preserved", "text/plain")
    # Local sender records are in-memory objects in this fault-injection test.
    s.sender = make_services(s.settings).sender
    forget_family(s, family)
    assert s.store.get_student(other_student.id) is not None
    assert s.grade_log.by_student(student.id) == []
    assert s.store.list_records(family.id) == []
    remaining = client.scan(TableName="repaso")["Items"]
    assert not any(row["pk"]["S"].startswith(("SESSION#", "ITEM#")) for row in remaining)
    versions = media.list_object_versions(
        Bucket="repaso-synthetic-media", Prefix=f"media/{family.id}/"
    )
    assert versions.get("Versions", []) == []
    assert s.media.get(f"media/{other.id}/page") == b"preserved"


def test_erasure_resumes_after_partial_delete_and_finds_an_orphaned_copy(
    cloud_services, monkeypatch
):
    from repaso.tools import state_dynamo

    s, client, _ = cloud_services
    family, student = seed_family(s.store)
    other, _ = seed_family(s.store, "f2", "200")
    seed_mcqs(s, family.id)
    # A prior dual write lost its family index but retained the owned primary.
    client.delete_item(
        TableName="repaso",
        Key={"pk": {"S": f"FAMILY#{family.id}"}, "sk": {"S": f"STUDENT#{student.id}"}},
    )
    original = state_dynamo.delete_row
    calls = 0

    def interrupted(*args):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise ConnectionError("injected partial erasure")
        original(*args)

    monkeypatch.setattr(state_dynamo, "delete_row", interrupted)
    with pytest.raises(ConnectionError):
        forget_family(s, family)
    assert s.store.get_family(family.id) is not None
    forget_family(s, family)
    assert s.store.get_family(family.id) is None and s.store.get_student(student.id) is None
    assert s.store.get_family(other.id) is not None
    assert not s.store.list_family_items(family.id)


@pytest.mark.asyncio
async def test_the_answer_journal_reaches_dynamodb_with_the_tables_ttl_attribute(cloud_services):
    s, client, _ = cloud_services
    family, student = seed_family(s.store)
    seed_mcqs(s, family.id)
    await start_daily_session(s, family, student)
    await handle_answer(s, family, student, "1", 45, response_id="first")

    row = client.get_item(
        TableName="repaso",
        Key={"pk": {"S": f"DATA#{family.id}"}, "sk": {"S": "answer#first"}},
    )["Item"]
    stamp = int(row["expires_at"]["N"])
    assert stamp == expiry_stamp(s.clock.now())
    assert stamp == int(float(row["doc"]["M"]["payload"]["M"]["expires_at"]["N"]))


@pytest.mark.asyncio
async def test_the_attempt_ledger_is_written_without_a_horizon(cloud_services):
    s, client, _ = cloud_services
    family, student = seed_family(s.store)
    seed_mcqs(s, family.id)
    await start_daily_session(s, family, student)
    await handle_answer(s, family, student, "1", 45, response_id="first")

    episodes = client.query(
        TableName="repaso",
        KeyConditionExpression="pk = :pk AND begins_with(sk, :sk)",
        ExpressionAttributeValues={
            ":pk": {"S": f"DATA#{family.id}"},
            ":sk": {"S": "episode#"},
        },
    )["Items"]
    assert len(episodes) == 1
    assert "expires_at" not in episodes[0]


@pytest.mark.asyncio
async def test_a_sitting_reaches_dynamodb_with_the_tables_ttl_attribute(cloud_services):
    s, client, _ = cloud_services
    family, student = seed_family(s.store)
    seed_mcqs(s, family.id)
    opened = start_sitting(s, family, student)
    item = current_item(s, opened.session)
    await handle_study_text(s, family, item.answer_key, 9.0, "m1")

    rows = client.query(
        TableName="repaso",
        KeyConditionExpression="pk = :pk AND begins_with(sk, :sk)",
        ExpressionAttributeValues={":pk": {"S": f"DATA#{family.id}"}, ":sk": {"S": "study#"}},
    )["Items"]
    assert len(rows) == 1
    stamp = int(rows[0]["expires_at"]["N"])
    assert stamp == int(float(rows[0]["doc"]["M"]["payload"]["M"]["expires_at"]["N"]))
    assert stamp > s.clock.now().timestamp()


@pytest.mark.asyncio
async def test_the_turn_window_reaches_dynamodb_with_the_tables_ttl_attribute(cloud_services):
    s, client, _ = cloud_services
    family, student = seed_family(s.store)
    seed_mcqs(s, family.id)
    start_sitting(s, family, student)
    s.models[ModelRole.STRUCTURED] = LocalPlaybackModel()
    s.models[ModelRole.GENERATE] = LocalPlaybackModel()
    s.models[ModelRole.STRUCTURED].enqueue(
        {
            "intent": "explanation",
            "speaker": "child",
            "asked_for": "que se lo explique",
            "answer_text": "",
        }
    )
    s.models[ModelRole.GENERATE].enqueue({"text": "Parte la barra.", "approach": "bar split"})
    await handle_study_text(s, family, "no entiendo", 9.0, "m1")

    rows = client.query(
        TableName="repaso",
        KeyConditionExpression="pk = :pk AND begins_with(sk, :sk)",
        ExpressionAttributeValues={":pk": {"S": f"DATA#{family.id}"}, ":sk": {"S": "turn#"}},
    )["Items"]
    assert len(rows) == 1
    assert int(rows[0]["expires_at"]["N"]) > s.clock.now().timestamp()
