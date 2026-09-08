from pathlib import Path

import pytest

from repaso.config.models import ModelRole
from repaso.config.settings import Settings
from repaso.tools.cassette import CassetteEntry, CassetteWriter
from repaso.tools.cassette_model import CassetteModel
from repaso.tools.guardrails import DEFAULT_GUARDRAIL_VERSION
from repaso.tools.llm import (
    BLOCKED_OUTPUT_REPLACEMENT,
    SYNCHRONOUS_SCREENING,
    LocalPlaybackModel,
    PlaybackExhausted,
    build_model,
)
from repaso.tools.recording_model import RecordingModel


def user_message(text: str) -> dict:
    return {"role": "user", "content": [{"text": text}]}


async def collect(stream) -> list[dict]:
    return [event async for event in stream]


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


class StubBedrockModel:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


@pytest.fixture
def stub_bedrock(monkeypatch):
    monkeypatch.setattr("strands.models.bedrock.BedrockModel", StubBedrockModel)


def deployed(tmp_path, **overrides) -> Settings:
    return Settings(aws_region="us-east-1", local_mode=False, local_data_dir=tmp_path, **overrides)


def write_cassette(tmp_path) -> Path:
    path = tmp_path / "cassette.jsonl"
    writer = CassetteWriter(path)
    writer.append(CassetteEntry(role="judge", kind="stream", text="de judge"))
    writer.append(CassetteEntry(role="generate", kind="stream", text="de generate"))
    return path


async def test_build_model_replays_the_cassette_entries_of_its_own_role(tmp_path):
    path = write_cassette(tmp_path)
    settings = Settings(local_mode=True, local_data_dir=tmp_path, cassette_path=path)

    model = build_model(ModelRole.JUDGE, settings)

    assert isinstance(model, CassetteModel)
    events = await collect(model.stream([user_message("hola")]))
    assert events[2] == {"contentBlockDelta": {"delta": {"text": "de judge"}}}


def test_a_provided_playback_still_wins_over_a_cassette(tmp_path):
    settings = Settings(
        local_mode=True, local_data_dir=tmp_path, cassette_path=write_cassette(tmp_path)
    )
    playback = LocalPlaybackModel(["scripted"])

    assert build_model(ModelRole.JUDGE, settings, playback) is playback


def test_the_cassette_file_is_read_once_however_many_roles_ask_for_it(tmp_path, monkeypatch):
    settings = Settings(
        local_mode=True, local_data_dir=tmp_path, cassette_path=write_cassette(tmp_path)
    )
    reads: list[Path] = []
    monkeypatch.setattr("repaso.tools.llm.load_cassette", lambda path: reads.append(path) or [])

    for role in ModelRole:
        build_model(role, settings)

    assert reads == [settings.cassette_path]


def test_build_model_returns_bedrock_when_no_cassette_is_being_recorded(tmp_path, stub_bedrock):
    model = build_model(ModelRole.JUDGE, deployed(tmp_path))

    assert isinstance(model, StubBedrockModel)
    assert model.kwargs["region_name"] == "us-east-1"


def test_build_model_wraps_bedrock_in_the_recorder_when_a_record_path_is_set(
    tmp_path, stub_bedrock
):
    path = tmp_path / "recorded.jsonl"

    model = build_model(ModelRole.JUDGE, deployed(tmp_path, record_cassette_path=path))

    assert isinstance(model, RecordingModel)
    assert isinstance(model.inner, StubBedrockModel)


def test_every_role_records_into_one_writer_for_the_same_file(tmp_path, stub_bedrock):
    settings = deployed(tmp_path, record_cassette_path=tmp_path / "recorded.jsonl")

    writers = {build_model(role, settings)._writer for role in ModelRole}

    assert len(writers) == 1


def test_build_model_omits_guardrail_arguments_when_none_is_configured(tmp_path, stub_bedrock):
    model = build_model(ModelRole.GENERATE, deployed(tmp_path))

    assert "guardrail_id" not in model.kwargs
    assert "guardrail_version" not in model.kwargs


def test_build_model_forwards_the_configured_guardrail(tmp_path, stub_bedrock):
    settings = deployed(tmp_path, guardrail_id="gr-abc123", guardrail_version="2")

    model = build_model(ModelRole.JUDGE, settings)

    assert model.kwargs["guardrail_id"] == "gr-abc123"
    assert model.kwargs["guardrail_version"] == "2"


def test_build_model_falls_back_to_the_draft_version(tmp_path, stub_bedrock):
    model = build_model(ModelRole.PROBE, deployed(tmp_path, guardrail_id="gr-abc123"))

    assert model.kwargs["guardrail_version"] == DEFAULT_GUARDRAIL_VERSION


def test_build_model_screens_the_output_side_explicitly(tmp_path, stub_bedrock):
    model = build_model(ModelRole.GENERATE, deployed(tmp_path, guardrail_id="gr-abc123"))

    assert model.kwargs["guardrail_redact_output"] is True
    assert model.kwargs["guardrail_redact_output_message"] == BLOCKED_OUTPUT_REPLACEMENT
    assert model.kwargs["guardrail_stream_processing_mode"] == SYNCHRONOUS_SCREENING


def test_the_output_replacement_never_leaks_the_blocked_text(tmp_path, stub_bedrock):
    model = build_model(ModelRole.JUDGE, deployed(tmp_path, guardrail_id="gr-abc123"))

    assert "[Assistant output redacted.]" not in model.kwargs.values()
    assert BLOCKED_OUTPUT_REPLACEMENT.startswith("Prefiero no responder")


def test_an_unconfigured_guardrail_leaves_the_output_side_untouched(tmp_path, stub_bedrock):
    model = build_model(ModelRole.GENERATE, deployed(tmp_path))

    assert "guardrail_redact_output" not in model.kwargs
