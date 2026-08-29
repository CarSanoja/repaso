import json

import pytest

from repaso.config.settings import Settings, clear_settings_cache
from repaso.lambdas import bootstrap
from repaso.tools.state_local import LocalStateStore
from repaso.tools.telegram import TelegramSender

TELEGRAM_PAYLOAD = {"webhook_secret": "from-secrets", "bot_token": "bot-123"}


class FakeSecretsClient:
    def __init__(self, payloads: dict[str, str]) -> None:
        self.payloads = payloads
        self.requests: list[str] = []

    def get_secret_value(self, SecretId: str) -> dict[str, str]:
        self.requests.append(SecretId)
        if SecretId not in self.payloads:
            raise KeyError(SecretId)
        return {"SecretString": self.payloads[SecretId]}


@pytest.fixture
def secrets(monkeypatch):
    client = FakeSecretsClient(
        {
            "repaso/telegram": json.dumps(TELEGRAM_PAYLOAD),
            "repaso/judge": json.dumps({"code": "JUDGE9"}),
        }
    )
    monkeypatch.setattr("repaso.config.clients.secrets_client", lambda: client)
    return client


def test_secret_fields_are_read_from_a_json_secret(lambda_env, secrets):
    assert bootstrap._secret_field("repaso/telegram", "webhook_secret") == "from-secrets"
    assert bootstrap._secret_field("repaso/telegram", "bot_token") == "bot-123"
    assert bootstrap._secret_field("repaso/telegram", "absent") == ""


def test_a_plain_string_secret_is_used_as_the_value(lambda_env, monkeypatch):
    client = FakeSecretsClient({"repaso/judge": "JUDGE9"})
    monkeypatch.setattr("repaso.config.clients.secrets_client", lambda: client)
    assert bootstrap._secret_field("repaso/judge", "code") == "JUDGE9"


def test_the_environment_wins_over_the_secret_store(lambda_env, secrets, monkeypatch):
    monkeypatch.setenv("REPASO_TELEGRAM_SECRET", "from-env")
    container = bootstrap.build_lambda_container()
    assert container.telegram_secret == "from-env"
    assert container.judge_code == "JUDGE9"
    assert sorted(set(secrets.requests)) == ["repaso/judge", "repaso/telegram"]


def test_secrets_are_not_read_when_there_is_no_client(lambda_env):
    assert bootstrap._secret_field("repaso/telegram", "webhook_secret") == ""
    assert bootstrap.build_lambda_container().telegram_secret == ""


def test_the_container_carries_the_secret_material_it_resolved(lambda_env, secrets):
    container = bootstrap.build_lambda_container()
    assert container.telegram_secret == "from-secrets"
    assert container.judge_code == "JUDGE9"
    assert isinstance(container.store, LocalStateStore)


def test_a_deployed_container_builds_its_telegram_sender_from_the_secret(secrets, tmp_path):
    clear_settings_cache()
    settings = Settings(aws_region="us-east-1", local_mode=False, local_data_dir=tmp_path)
    container = bootstrap.build_lambda_container(settings)
    assert isinstance(container.sender, TelegramSender)
    assert container.telegram_secret == "from-secrets"


def test_the_container_is_built_once_and_cleared_by_reset(lambda_env):
    first = bootstrap.container()
    assert bootstrap.container() is first
    bootstrap.reset()
    assert bootstrap.container() is not first


def test_the_store_and_the_publisher_are_built_once(lambda_env):
    store = bootstrap.store()
    publisher = bootstrap.publisher()
    assert bootstrap.store() is store
    assert bootstrap.publisher() is publisher
    bootstrap.reset()
    assert bootstrap.store() is not store
    assert bootstrap.publisher() is not publisher
