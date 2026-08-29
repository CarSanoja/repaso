from datetime import UTC, datetime

import pytest

from repaso.runtime.errors import ErrorCode, InvocationError
from repaso.runtime.payload import (
    AnswerPayload,
    InvocationRequest,
    MaterialPayload,
    parse_request,
    validate,
)
from repaso.schemas.events import DomainEvent, EventKind

NOW = datetime(2026, 9, 1, 19, 0, tzinfo=UTC)


def test_minimal_payload_only_needs_a_kind():
    request = parse_request({"kind": "daily_close"})

    assert request.kind is EventKind.DAILY_CLOSE
    assert request.family_id is None
    assert request.payload == {}


def test_a_published_domain_event_validates_unchanged():
    event = DomainEvent(
        kind=EventKind.RESPONSE_RECEIVED,
        family_id="f1",
        idempotency_key="chat#1",
        occurred_at=NOW,
        payload={"student_id": "s-f1", "text": "1/2"},
    )

    request = parse_request(event.model_dump(mode="json"))

    assert request.kind is EventKind.RESPONSE_RECEIVED
    assert request.family_id == "f1"
    assert request.idempotency_key == "chat#1"
    assert request.payload == {"student_id": "s-f1", "text": "1/2"}


@pytest.mark.parametrize("payload", [[], "daily_close", None, 7])
def test_non_object_payloads_are_rejected(payload):
    with pytest.raises(InvocationError) as caught:
        parse_request(payload)

    assert caught.value.code is ErrorCode.INVALID_PAYLOAD


@pytest.mark.parametrize("payload", [{}, {"kind": ""}, {"kind": 3}, {"family_id": "f1"}])
def test_a_missing_or_non_string_kind_is_an_invalid_payload(payload):
    with pytest.raises(InvocationError) as caught:
        parse_request(payload)

    assert caught.value.code is ErrorCode.INVALID_PAYLOAD
    assert "kind" in caught.value.message


def test_an_unrecognised_kind_is_reported_as_unknown_not_invalid():
    with pytest.raises(InvocationError) as caught:
        parse_request({"kind": "material_deleted"})

    assert caught.value.code is ErrorCode.UNKNOWN_KIND
    assert "material_deleted" in caught.value.message
    assert "daily_close" in caught.value.message


def test_unexpected_top_level_fields_are_refused():
    with pytest.raises(InvocationError) as caught:
        parse_request({"kind": "daily_close", "prompt": "please grade everything"})

    assert caught.value.code is ErrorCode.INVALID_PAYLOAD
    assert "prompt" in caught.value.message


def test_request_payload_must_be_an_object():
    with pytest.raises(InvocationError) as caught:
        parse_request({"kind": "daily_close", "payload": ["s1"]})

    assert caught.value.code is ErrorCode.INVALID_PAYLOAD
    assert "payload" in caught.value.message


def test_material_payload_needs_exactly_one_content_source():
    with pytest.raises(InvocationError) as caught:
        validate(MaterialPayload, {"student_id": "s1", "media_kind": "pdf"})
    assert caught.value.code is ErrorCode.INVALID_PAYLOAD

    with pytest.raises(InvocationError):
        validate(
            MaterialPayload,
            {
                "student_id": "s1",
                "media_kind": "pdf",
                "content_b64": "aGk=",
                "media_ref": "media/f1/m1",
            },
        )

    parsed = validate(
        MaterialPayload, {"student_id": "s1", "media_kind": "pdf", "content_b64": "aGk="}
    )
    assert parsed.media_ref is None


def test_answer_payload_rejects_negative_latency_and_defaults_to_zero():
    with pytest.raises(InvocationError) as caught:
        validate(AnswerPayload, {"student_id": "s1", "text": "1/2", "latency_seconds": -4.0})
    assert "latency_seconds" in caught.value.message

    assert validate(AnswerPayload, {"student_id": "s1", "text": "1/2"}).latency_seconds == 0.0


def test_validation_messages_name_the_offending_field():
    with pytest.raises(InvocationError) as caught:
        validate(InvocationRequest, {"kind": "daily_close", "occurred_at": "not-a-date"})

    assert "occurred_at" in caught.value.message
