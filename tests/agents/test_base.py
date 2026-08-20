import pytest
from pydantic import BaseModel

from repaso.agents.base import StructuredCallFailed, structured, user_message
from repaso.tools.llm import LocalPlaybackModel, PlaybackExhausted


class Verdict(BaseModel):
    ok: bool
    reason: str


async def test_structured_returns_the_parsed_output():
    model = LocalPlaybackModel([{"ok": True, "reason": "fits"}])
    result = await structured(model, Verdict, "judge", "evaluate this")
    assert result == Verdict(ok=True, reason="fits")


async def test_structured_propagates_playback_exhaustion():
    model = LocalPlaybackModel([])
    with pytest.raises(PlaybackExhausted):
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
