from typing import Any

import pytest
from pydantic import BaseModel
from strands.models.model import Model

from repaso.tools.model_limits import ModelLimitReached
from repaso.tools.retrying_model import RetryingModel


class Snippet(BaseModel):
    text: str


class Throttled(Exception):
    def __init__(self, code: str = "ThrottlingException") -> None:
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class FlakyModel(Model):
    def __init__(self, failures: int, error: Exception | None = None) -> None:
        self.failures = failures
        self.error = error or Throttled()
        self.attempts = 0
        self.config: dict[str, Any] = {"model_id": "us.amazon.nova-micro-v1:0"}
        self.evidence_origin = "live"

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return self.config

    def _admit(self) -> None:
        self.attempts += 1
        if self.attempts <= self.failures:
            raise self.error

    async def stream(self, messages: Any, *args: Any, **kwargs: Any):
        self._admit()
        yield {"contentBlockDelta": {"delta": {"text": "hola"}}}

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs: Any):
        self._admit()
        yield {"output": output_model(text="hola")}


def user_message(text: str) -> dict:
    return {"role": "user", "content": [{"text": text}]}


def patient(inner: Model, attempts: int = 4) -> RetryingModel:
    waited: list[float] = []

    async def sleep(seconds: float) -> None:
        waited.append(seconds)

    model = RetryingModel(inner, attempts=attempts, sleep=sleep, jitter=lambda: 0.5)
    model.slept = waited
    return model


async def structured(model: Model) -> Snippet:
    events = [event async for event in model.structured_output(Snippet, [user_message("hola")])]
    return events[-1]["output"]


async def test_a_throttled_call_is_answered_after_the_wait():
    inner = FlakyModel(failures=2)

    reply = await structured(patient(inner))

    assert reply.text == "hola"
    assert inner.attempts == 3


async def test_the_wait_grows_between_attempts():
    model = patient(FlakyModel(failures=2))

    await structured(model)

    assert model.slept == [2.0, 4.0]
    assert model.waits == [2.0, 4.0]


async def test_a_stream_is_retried_the_same_way():
    inner = FlakyModel(failures=1)

    events = [event async for event in patient(inner).stream([user_message("hola")])]

    assert events[-1]["contentBlockDelta"]["delta"]["text"] == "hola"
    assert inner.attempts == 2


async def test_an_error_the_provider_will_not_fix_is_raised_at_once():
    inner = FlakyModel(failures=1, error=Throttled("ValidationException"))

    with pytest.raises(Throttled):
        await structured(patient(inner))

    assert inner.attempts == 1


async def test_the_last_attempt_raises_what_the_provider_said():
    inner = FlakyModel(failures=9)

    with pytest.raises(Throttled):
        await structured(patient(inner, attempts=3))

    assert inner.attempts == 3


async def test_a_limit_the_harness_raised_is_not_retried_forever():
    inner = FlakyModel(failures=9, error=ModelLimitReached("daily allowance exhausted"))

    with pytest.raises(ModelLimitReached):
        await structured(patient(inner))

    assert inner.attempts == 1


async def test_the_wrapper_is_the_model_it_wraps():
    inner = FlakyModel(failures=0)
    model = patient(inner)

    model.update_config(temperature=0.0)

    assert model.get_config()["model_id"] == "us.amazon.nova-micro-v1:0"
    assert model.get_config()["temperature"] == 0.0
    assert model.evidence_origin == "live"


def test_a_retrying_model_needs_at_least_one_attempt():
    with pytest.raises(ValueError):
        RetryingModel(FlakyModel(failures=0), attempts=0)
