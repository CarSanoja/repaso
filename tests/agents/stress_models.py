from collections.abc import AsyncGenerator, Callable
from typing import Any

from botocore.exceptions import ClientError, ReadTimeoutError
from pydantic import BaseModel
from strands.types.exceptions import ModelThrottledException

BEDROCK_ENDPOINT = "https://bedrock-runtime.us-east-1.amazonaws.com"
THROTTLE_TEXT = "Too many requests, please wait before trying again."
OPERATION = "ConverseStream"


def throttling_error() -> Exception:
    return ModelThrottledException(
        str(
            ClientError(
                {"Error": {"Code": "ThrottlingException", "Message": THROTTLE_TEXT}}, OPERATION
            )
        )
    )


def read_timeout_error() -> Exception:
    return ReadTimeoutError(endpoint_url=BEDROCK_ENDPOINT)


class FailingModel:
    def __init__(self, make_error: Callable[[], Exception]) -> None:
        self._make_error = make_error
        self.calls = 0

    def structured_output(
        self, output_model: type[BaseModel], prompt: Any, system_prompt: str | None = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        self.calls += 1
        error = self._make_error()

        async def failing() -> AsyncGenerator[dict[str, Any], None]:
            raise error
            yield {}

        return failing()


class MalformedModel:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.calls = 0

    def structured_output(
        self, output_model: type[BaseModel], prompt: Any, system_prompt: str | None = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        self.calls += 1
        payload = self._payload

        async def validating() -> AsyncGenerator[dict[str, Any], None]:
            yield {"output": output_model(**payload)}

        return validating()


def throttled_model() -> FailingModel:
    return FailingModel(throttling_error)


def timed_out_model() -> FailingModel:
    return FailingModel(read_timeout_error)


STRESSES = ("throttled", "timed_out", "malformed")


def stressed(kind: str, payload: dict[str, Any]):
    if kind == "throttled":
        return throttled_model()
    if kind == "timed_out":
        return timed_out_model()
    return MalformedModel(payload)
