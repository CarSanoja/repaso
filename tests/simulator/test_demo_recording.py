from pathlib import Path

from repaso.config.models import ModelRole
from repaso.simulator import demo_recording
from repaso.simulator.demo_recording import live_model_settings, recording_models
from repaso.simulator.demo_scenario import scenario_settings
from repaso.tools.llm import LocalPlaybackModel
from repaso.tools.retrying_model import RetryingModel

REGION = "us-east-1"


def test_the_models_are_the_only_part_of_the_run_that_leaves_the_machine(tmp_path):
    destination = tmp_path / "recorded.jsonl"

    settings = live_model_settings(scenario_settings(tmp_path / "state"), REGION, destination)

    assert settings.local_mode is False
    assert settings.aws_region == REGION
    assert settings.record_cassette_path == destination
    assert settings.cassette_path is None
    assert settings.local_data_dir == tmp_path / "state"


def test_every_role_is_recorded_behind_a_retry(tmp_path, monkeypatch):
    asked: list[tuple[ModelRole, Path | None]] = []

    def fake_build(role: ModelRole, settings) -> LocalPlaybackModel:
        asked.append((role, settings.record_cassette_path))
        return LocalPlaybackModel()

    monkeypatch.setattr(demo_recording, "build_model", fake_build)
    destination = tmp_path / "recorded.jsonl"

    models = recording_models(scenario_settings(tmp_path / "state"), REGION, destination)

    assert set(models) == set(ModelRole)
    assert all(isinstance(model, RetryingModel) for model in models.values())
    assert asked == [(role, destination) for role in ModelRole]
