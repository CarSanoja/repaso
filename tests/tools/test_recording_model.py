from typing import Any

import pytest
from pydantic import BaseModel
from strands.models.model import Model

from repaso.tools.cassette import CassetteWriter, load_cassette
from repaso.tools.cassette_model import CassetteExhausted, CassetteModel
from repaso.tools.llm import LocalPlaybackModel, PlaybackExhausted
from repaso.tools.recording_model import RecordingModel


class Verdict(BaseModel):
    label: str
    score: float


class Snippet(BaseModel):
    text: str


class MetadataModel(Model):
    def __init__(self, text: str, usage: dict[str, int] | None) -> None:
        self.text = text
        self.usage = usage
        self.config: dict[str, Any] = {}

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return self.config

    async def stream(self, messages: Any, *args: Any, **kwargs: Any):
        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockDelta": {"delta": {"text": self.text}}}
        yield {"messageStop": {"stopReason": "end_turn"}}
        if self.usage is not None:
            yield {"metadata": {"usage": self.usage}}

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs: Any):
        if self.usage is not None:
            yield {"event": {"metadata": {"usage": self.usage}}}
        yield {"output": output_model(text=self.text)}


class SilentModel(Model):
    def update_config(self, **model_config: Any) -> None:
        return None

    def get_config(self) -> dict[str, Any]:
        return {}

    async def stream(self, messages: Any, *args: Any, **kwargs: Any):
        yield {"messageStop": {"stopReason": "end_turn"}}

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs: Any):
        yield {"callback": {"delta": "pensando"}}


def user_message(text: str) -> dict:
    return {"role": "user", "content": [{"text": text}]}


async def collect(stream) -> list[dict]:
    return [event async for event in stream]


async def structured(model: Model, schema: type[BaseModel]) -> BaseModel:
    events = [event async for event in model.structured_output(schema, [user_message("hola")])]
    return events[-1]["output"]


def recorder(tmp_path, inner: Model, role: str = "judge") -> RecordingModel:
    return RecordingModel(inner, CassetteWriter(tmp_path / "cassette.jsonl"), role)


async def test_every_event_reaches_the_caller_unchanged(tmp_path):
    inner = LocalPlaybackModel(["cuarenta y dos"])
    events = await collect(recorder(tmp_path, inner).stream([user_message("hola")]))

    assert events[2] == {"contentBlockDelta": {"delta": {"text": "cuarenta y dos"}}}
    assert inner.calls == [{"kind": "stream", "system_prompt": None, "message_count": 1}]


async def test_a_recorded_run_replays_to_the_same_outputs(tmp_path):
    path = tmp_path / "cassette.jsonl"
    inner = LocalPlaybackModel(
        ["primera respuesta", {"label": "ok", "score": 0.9}, {"text": "una pista"}]
    )
    recording = RecordingModel(inner, CassetteWriter(path), "judge")

    live_stream = await collect(recording.stream([user_message("hola")]))
    live_verdict = await structured(recording, Verdict)
    live_snippet = await structured(recording, Snippet)

    replay = CassetteModel(load_cassette(path), "judge")
    assert await collect(replay.stream([user_message("otro prompt")])) == live_stream
    assert await structured(replay, Verdict) == live_verdict
    assert await structured(replay, Snippet) == live_snippet


async def test_the_cassette_holds_one_entry_per_call_in_order(tmp_path):
    path = tmp_path / "cassette.jsonl"
    inner = LocalPlaybackModel(["texto", {"label": "ok", "score": 0.5}])
    recording = RecordingModel(inner, CassetteWriter(path), "probe")

    await collect(recording.stream([user_message("hola")]))
    await structured(recording, Verdict)

    entries = load_cassette(path)
    assert [(entry.role, entry.kind, entry.output_model) for entry in entries] == [
        ("probe", "stream", None),
        ("probe", "structured_output", "Verdict"),
    ]
    assert entries[0].text == "texto"
    assert entries[1].payload == {"label": "ok", "score": 0.5}
    assert all(entry.latency_ms >= 0.0 for entry in entries)


async def test_usage_is_taken_from_the_metadata_event_of_a_stream(tmp_path):
    inner = MetadataModel("hola", {"inputTokens": 311, "outputTokens": 27, "totalTokens": 338})
    await collect(recorder(tmp_path, inner).stream([user_message("hola")]))

    usage = load_cassette(tmp_path / "cassette.jsonl")[0].usage
    assert usage.input_tokens == 311
    assert usage.output_tokens == 27


async def test_usage_is_taken_from_the_chunk_a_structured_call_forwards(tmp_path):
    inner = MetadataModel("una pista", {"inputTokens": 90, "outputTokens": 12})
    await structured(recorder(tmp_path, inner), Snippet)

    usage = load_cassette(tmp_path / "cassette.jsonl")[0].usage
    assert (usage.input_tokens, usage.output_tokens) == (90, 12)


async def test_a_model_that_reports_no_usage_records_none(tmp_path):
    inner = MetadataModel("hola", None)
    await collect(recorder(tmp_path, inner).stream([user_message("hola")]))

    assert load_cassette(tmp_path / "cassette.jsonl")[0].usage is None


async def test_a_structured_call_that_yields_no_output_records_nothing(tmp_path):
    path = tmp_path / "cassette.jsonl"
    recording = RecordingModel(SilentModel(), CassetteWriter(path), "judge")

    events = [event async for event in recording.structured_output(Snippet, [user_message("x")])]

    assert events == [{"callback": {"delta": "pensando"}}]
    assert path.exists() is False

    with pytest.raises(CassetteExhausted, match="Snippet"):
        await structured(CassetteModel([], "judge"), Snippet)


async def test_a_failing_call_is_not_recorded_and_the_error_reaches_the_caller(tmp_path):
    path = tmp_path / "cassette.jsonl"
    recording = RecordingModel(LocalPlaybackModel(), CassetteWriter(path), "judge")

    with pytest.raises(PlaybackExhausted):
        await collect(recording.stream([user_message("hola")]))

    assert path.exists() is False


def test_config_and_attributes_reach_the_wrapped_model(tmp_path):
    inner = MetadataModel("hola", None)
    recording = recorder(tmp_path, inner)
    recording.update_config(temperature=0.2)

    assert recording.get_config() == {"temperature": 0.2}
    assert recording.text == "hola"
