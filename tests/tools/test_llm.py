import pytest
from pydantic import BaseModel

from repaso.config.models import ModelRole
from repaso.config.settings import Settings
from repaso.tools.llm import LocalPlaybackModel, PlaybackExhausted, build_model


class Verdict(BaseModel):
    label: str
    score: float


def user_message(text: str) -> dict:
    return {"role": "user", "content": [{"text": text}]}


async def collect(stream) -> list[dict]:
    return [event async for event in stream]


async def test_stream_replays_scripted_text_as_converse_events():
    model = LocalPlaybackModel(["cuarenta y dos"])
    events = await collect(model.stream([user_message("hola")], system_prompt="tutor"))
    assert events == [
        {"messageStart": {"role": "assistant"}},
        {"contentBlockStart": {"start": {}}},
        {"contentBlockDelta": {"delta": {"text": "cuarenta y dos"}}},
        {"contentBlockStop": {}},
        {"messageStop": {"stopReason": "end_turn"}},
    ]


async def test_structured_output_accepts_dict_and_instance_entries():
    model = LocalPlaybackModel()
    model.enqueue({"label": "ok", "score": 0.9})
    model.enqueue(Verdict(label="flawed", score=0.1))
    prompt = [user_message("evalua")]

    first = [event async for event in model.structured_output(Verdict, prompt)]
    second = [event async for event in model.structured_output(Verdict, prompt)]

    assert first[-1]["output"] == Verdict(label="ok", score=0.9)
    assert isinstance(first[-1]["output"], Verdict)
    assert second[-1]["output"].label == "flawed"


async def test_empty_script_raises_playback_exhausted_on_stream():
    model = LocalPlaybackModel()
    with pytest.raises(PlaybackExhausted):
        await collect(model.stream([user_message("hola")]))


async def test_empty_script_raises_playback_exhausted_on_structured_output():
    model = LocalPlaybackModel()
    with pytest.raises(PlaybackExhausted):
        [event async for event in model.structured_output(Verdict, [user_message("hola")])]


async def test_kind_mismatch_raises_playback_exhausted():
    stream_model = LocalPlaybackModel([{"label": "ok", "score": 1.0}])
    with pytest.raises(PlaybackExhausted, match="must be str"):
        await collect(stream_model.stream([user_message("hola")]))

    structured_model = LocalPlaybackModel(["plain text"])
    with pytest.raises(PlaybackExhausted, match="must be Verdict"):
        [event async for event in structured_model.structured_output(Verdict, [user_message("x")])]


async def test_calls_record_kind_prompt_and_message_count():
    model = LocalPlaybackModel(["uno", {"label": "ok", "score": 0.5}])
    await collect(model.stream([user_message("a")], system_prompt="tutor"))
    prompt = [user_message("a"), user_message("b")]
    [event async for event in model.structured_output(Verdict, prompt)]

    assert model.calls == [
        {"kind": "stream", "system_prompt": "tutor", "message_count": 1},
        {"kind": "structured_output", "system_prompt": None, "message_count": 2},
    ]


def test_update_config_stores_and_get_config_returns_it():
    model = LocalPlaybackModel()
    model.update_config(temperature=0.2)
    model.update_config(max_tokens=512)
    assert model.get_config() == {"temperature": 0.2, "max_tokens": 512}


def test_build_model_returns_local_playback_in_local_mode(settings: Settings):
    model = build_model(ModelRole.GENERATE, settings)
    assert isinstance(model, LocalPlaybackModel)
    assert model.calls == []


def test_build_model_honors_provided_playback(tmp_path):
    settings = Settings(local_mode=True, local_data_dir=tmp_path / "local_data")
    playback = LocalPlaybackModel(["scripted"])
    assert build_model(ModelRole.JUDGE, settings, playback) is playback


async def test_built_local_model_replays_the_provided_script(settings: Settings):
    playback = LocalPlaybackModel(["listo"])
    model = build_model(ModelRole.STRUCTURED, settings, playback)
    events = await collect(model.stream([user_message("hola")]))
    assert events[2] == {"contentBlockDelta": {"delta": {"text": "listo"}}}
    with pytest.raises(PlaybackExhausted):
        await collect(model.stream([user_message("otra vez")]))
