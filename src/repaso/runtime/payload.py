from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, ValidationError, model_validator

from repaso.runtime.errors import ErrorCode, InvocationError
from repaso.schemas.channel import MediaKind
from repaso.schemas.common import StrictBaseModel
from repaso.schemas.events import EventKind


class InvocationRequest(StrictBaseModel):
    kind: EventKind
    family_id: str | None = None
    idempotency_key: str = ""
    occurred_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class StudentScoped(StrictBaseModel):
    student_id: str


class MaterialPayload(StudentScoped):
    media_kind: MediaKind
    material_id: str | None = None
    content_b64: str | None = None
    media_ref: str | None = None

    @model_validator(mode="after")
    def require_exactly_one_source(self) -> "MaterialPayload":
        if bool(self.content_b64) == bool(self.media_ref):
            raise ValueError("exactly one of content_b64 or media_ref is required")
        return self


class AnswerPayload(StudentScoped):
    text: str
    latency_seconds: float = Field(default=0.0, ge=0.0)


def describe(error: ValidationError) -> str:
    details = [
        f"{'.'.join(str(part) for part in item['loc']) or 'payload'}: {item['msg']}"
        for item in error.errors()
    ]
    return "; ".join(details)


def validate[Model: BaseModel](model: type[Model], data: dict[str, Any]) -> Model:
    try:
        return model.model_validate(data)
    except ValidationError as error:
        raise InvocationError(ErrorCode.INVALID_PAYLOAD, describe(error)) from error


def parse_request(payload: Any) -> InvocationRequest:
    if not isinstance(payload, dict):
        raise InvocationError(
            ErrorCode.INVALID_PAYLOAD,
            f"invocation payload must be an object, got {type(payload).__name__}",
        )
    kind = payload.get("kind")
    if not isinstance(kind, str) or not kind:
        raise InvocationError(
            ErrorCode.INVALID_PAYLOAD, "invocation payload must carry a string 'kind'"
        )
    try:
        EventKind(kind)
    except ValueError as error:
        known = ", ".join(sorted(member.value for member in EventKind))
        raise InvocationError(
            ErrorCode.UNKNOWN_KIND, f"unknown event kind '{kind}'; known kinds: {known}"
        ) from error
    return validate(InvocationRequest, payload)
