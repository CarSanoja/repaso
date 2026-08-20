from repaso.config.clients import dynamodb_client
from repaso.config.models import DEFAULT_MODELS, ModelRole, fallback_chain, model_for
from repaso.config.settings import Settings


def test_local_mode_derives_from_missing_region():
    assert Settings().local_mode is True


def test_region_turns_local_mode_off():
    assert Settings(aws_region="us-east-1").local_mode is False


def test_explicit_local_mode_wins_over_region():
    assert Settings(aws_region="us-east-1", local_mode=True).local_mode is True


def test_clients_return_none_in_local_mode():
    assert dynamodb_client() is None


def test_model_env_override(monkeypatch):
    monkeypatch.setenv("REPASO_MODEL_GENERATE", "custom-model")
    assert model_for(ModelRole.GENERATE) == "custom-model"


def test_fallback_chain_starts_with_primary():
    chain = fallback_chain(ModelRole.JUDGE)
    assert chain[0] == DEFAULT_MODELS[ModelRole.JUDGE]
    assert len(chain) >= 2


def test_threshold_bounds_fail_at_boot():
    try:
        Settings(grader_confidence_threshold=1.5)
    except ValueError:
        return
    raise AssertionError("out-of-range threshold must fail validation")
