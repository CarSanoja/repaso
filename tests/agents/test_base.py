import pytest
from pydantic import BaseModel, ValidationError

from repaso.agents.base import ModelOutput, StructuredCallFailed, structured, user_message
from repaso.tools.cassette_model import CassetteExhausted, CassetteModel
from repaso.tools.llm import LocalPlaybackModel, PlaybackExhausted


class Verdict(BaseModel):
    ok: bool
    reason: str


class Reported(ModelOutput):
    label: str
    reasons: list[str] = []
    counts: list[int] = []
    note: str | None = None


def test_a_list_a_model_left_null_reads_as_nothing_to_report():
    parsed = Reported(label="safe", reasons=None, counts=None)

    assert (parsed.reasons, parsed.counts) == ([], [])


def test_a_list_a_model_filled_survives_untouched():
    parsed = Reported(label="unsafe", reasons=["marker"], counts=[1, 2])

    assert (parsed.reasons, parsed.counts) == (["marker"], [1, 2])


def test_an_omitted_list_still_takes_its_default():
    assert Reported(label="safe").reasons == []


def test_null_is_still_refused_where_the_field_is_not_a_list():
    with pytest.raises(ValidationError):
        Reported(label=None)


async def test_structured_returns_the_parsed_output():
    model = LocalPlaybackModel([{"ok": True, "reason": "fits"}])
    result = await structured(model, Verdict, "judge", "evaluate this")
    assert result == Verdict(ok=True, reason="fits")


async def test_structured_propagates_playback_exhaustion():
    model = LocalPlaybackModel([])
    with pytest.raises(PlaybackExhausted):
        await structured(model, Verdict, "judge", "evaluate this")


async def test_structured_propagates_cassette_exhaustion():
    model = CassetteModel([], "judge")
    with pytest.raises(CassetteExhausted):
        await structured(model, Verdict, "judge", "evaluate this")


async def test_structured_wraps_model_errors():
    class BrokenModel:
        def structured_output(self, output_model, prompt, system_prompt=None):
            async def failing():
                raise RuntimeError("boom")
                yield {}

            return failing()

    with pytest.raises(StructuredCallFailed):
        await structured(BrokenModel(), Verdict, "judge", "evaluate this")


def test_user_message_shape():
    assert user_message("hola") == {"role": "user", "content": [{"text": "hola"}]}
