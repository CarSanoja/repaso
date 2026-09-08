"""What a preflight check reports, and how a read-only probe reads an AWS answer."""

from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from repaso.schemas.common import FrozenStrictModel

ABSENT = ("NotFound", "NoSuchEntity", "NonExistentQueue", "ValidationError")
DENIED = ("AccessDenied", "UnauthorizedOperation", "Forbidden")


class Status(StrEnum):
    OK = "ok"
    WARN = "warn"
    BLOCKER = "blocker"


class Finding(FrozenStrictModel):
    check: str
    status: Status
    detail: str
    remedy: str = ""


@runtime_checkable
class AwsSession(Protocol):
    region_name: str

    def client(self, service_name: str, **kwargs: Any) -> Any: ...


def code_of(error: Exception) -> str:
    response = getattr(error, "response", None) or {}
    return str(response.get("Error", {}).get("Code", type(error).__name__))


def absent(error: Exception) -> bool:
    return any(marker in code_of(error) for marker in ABSENT)


def denied(error: Exception) -> bool:
    return any(marker in code_of(error) for marker in DENIED)


def present(session: AwsSession, service: str, method: str, kwargs: dict[str, str]) -> bool | None:
    try:
        getattr(session.client(service), method)(**kwargs)
    except Exception as error:
        if absent(error):
            return False
        if denied(error):
            return None
        raise
    return True
