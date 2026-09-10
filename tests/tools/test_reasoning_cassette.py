from typing import Any

from pydantic import BaseModel
from strands.models.model import Model

from repaso.tools.cassette import CassetteWriter, load_cassette
from repaso.tools.cassette_model import CassetteModel
from repaso.tools.recording_model import RecordingModel

SONNET = "us.anthropic.claude-sonnet-4-6"
THOUGHT = ("s", "-t-r-a-w", "-b-e-r-r", "-y =", " 10 letters")
ANSWER = ("Let", " me count:", " 10 letters")
SIGNATURE = "EvcBCnUIERABGAIqQDV3kjRN3OFdzDfkB"


class Snippet(BaseModel):
    text: str


class ThinkingModel(Model):
    def __init__(self, model_id: str = SONNET) -> None:
        self._config: dict[str, Any] = {"model_id": model_id}

    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return self._config

    async def stream(self, messages: Any, *args: Any, **kwargs: Any):
        yield {"messageStart": {"role": "assistant"}}
        for fragment in THOUGHT:
            yield {"contentBlockDelta": {"delta": {"reasoningContent": {"text": fragment}}}}
        yield {"contentBlockDelta": {"delta": {"reasoningContent": {"signature": SIGNATURE}}}}
        yield {"contentBlockStop": {"contentBlockIndex": 0}}
        for fragment in ANSWER:
            yield {"contentBlockDelta": {"delta": {"text": fragment}}}
        yield {"contentBlockStop": {"contentBlockIndex": 1}}
        yield {"messageStop": {"stopReason": "end_turn"}}
        yield {
            "metadata": {
                "usage": {"inputTokens": 52, "outputTokens": 64, "totalTokens": 116},
                "metrics": {"latencyMs": 1393},
            }
        }

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs: Any):
        yield {"event": {"messageStop": {"stopReason": "tool_use"}}}
        yield {
            "event": {
                "metadata": {"usage": {"inputTokens": 671, "outputTokens": 37, "totalTokens": 708}}
            }
        }
        yield {"output": output_model(text="una pista")}


def user_message(text: str) -> dict:
    return {"role": "user", "content": [{"text": text}]}


async def record_a_thinking_stream(tmp_path):
    path = tmp_path / "cassette.jsonl"
    recording = RecordingModel(ThinkingModel(), CassetteWriter(path), "generate")
    async for _ in recording.stream([user_message("cuantas letras")]):
        pass
    return load_cassette(path)


async def test_the_reasoning_trace_is_recorded_beside_the_answer(tmp_path):
    entry = (await record_a_thinking_stream(tmp_path))[0]

    assert entry.reasoning == "".join(THOUGHT)
    assert entry.text == "".join(ANSWER)
    assert entry.model_id == SONNET
    assert entry.stop_reason == "end_turn"
    assert (entry.usage.input_tokens, entry.usage.output_tokens) == (52, 64)


async def test_a_thinking_call_replays_with_its_reasoning_intact(tmp_path):
    entries = await record_a_thinking_stream(tmp_path)
    replay = CassetteModel(entries, "generate")

    events = [event async for event in replay.stream([user_message("otra pregunta")])]
    deltas = [
        event["contentBlockDelta"]["delta"] for event in events if "contentBlockDelta" in event
    ]
    thought = [d["reasoningContent"]["text"] for d in deltas if "reasoningContent" in d]

    assert thought == ["".join(THOUGHT)]
    assert [delta["text"] for delta in deltas if "text" in delta] == ["".join(ANSWER)]
    assert replay.get_config()["model_id"] == SONNET
    assert events[-1] == {
        "metadata": {"usage": {"inputTokens": 52, "outputTokens": 64, "totalTokens": 116}}
    }


async def test_a_call_without_reasoning_replays_the_shape_it_always_had(tmp_path):
    path = tmp_path / "cassette.jsonl"
    recording = RecordingModel(ThinkingModel(), CassetteWriter(path), "structured")
    async for _ in recording.structured_output(Snippet, [user_message("hola")]):
        pass

    entry = load_cassette(path)[0]
    assert entry.reasoning is None
    assert entry.stop_reason == "tool_use"
    assert entry.model_id == SONNET
