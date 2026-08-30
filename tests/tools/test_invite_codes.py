from datetime import UTC, datetime

import pytest

from repaso.config.settings import Settings
from repaso.core.harness.clock import SimClock
from repaso.tools.invite_codes import (
    CACHE_TTL_SECONDS,
    INVITE_CODES_FILENAME,
    LocalInviteCodes,
    SecretsManagerInviteCodes,
    build_invite_codes,
    parse_codes,
)

START = datetime(2026, 9, 1, 19, 0, tzinfo=UTC)
SECRET_NAME = "repaso/pilot-invite-codes"


class StubSecrets:
    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.calls: list[str] = []

    def get_secret_value(self, SecretId: str) -> dict:
        self.calls.append(SecretId)
        return {"SecretString": self.payload}


def cloud_settings(tmp_path, codes: str = "") -> Settings:
    return Settings(
        local_mode=False,
        aws_region="us-east-1",
        local_data_dir=tmp_path,
        pilot_invite_codes=codes,
    )


def write_codes(tmp_path, contents: str):
    path = tmp_path / INVITE_CODES_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")
    return path


def test_codes_are_split_on_commas_and_newlines():
    assert parse_codes(" PILOTO-1, piloto-2 ,, ") == frozenset({"PILOTO-1", "piloto-2"})
    assert parse_codes("PILOTO-1\n\npiloto-2\n") == frozenset({"PILOTO-1", "piloto-2"})
    assert parse_codes("   ") == frozenset()


def test_the_local_source_reads_the_configured_value(tmp_path):
    source = LocalInviteCodes("PILOTO-1,PILOTO-2", tmp_path / INVITE_CODES_FILENAME)

    assert source.codes() == frozenset({"PILOTO-1", "PILOTO-2"})


def test_the_local_source_falls_back_to_a_file_of_one_code_per_line(tmp_path):
    write_codes(tmp_path, "PILOTO-1\nPILOTO-2\n\n")

    assert LocalInviteCodes("", tmp_path / INVITE_CODES_FILENAME).codes() == frozenset(
        {"PILOTO-1", "PILOTO-2"}
    )


def test_the_configured_value_overrides_the_file(tmp_path):
    write_codes(tmp_path, "FROM-FILE")

    source = LocalInviteCodes("FROM-SETTINGS", tmp_path / INVITE_CODES_FILENAME)

    assert source.codes() == frozenset({"FROM-SETTINGS"})


def test_nothing_configured_and_no_file_means_nobody_can_enroll(tmp_path):
    assert LocalInviteCodes("", tmp_path / INVITE_CODES_FILENAME).codes() == frozenset()


def test_the_cloud_source_reads_the_secret(monkeypatch):
    client = StubSecrets("PILOTO-1, PILOTO-2")
    monkeypatch.setattr("repaso.config.clients.secrets_client", lambda: client)

    source = SecretsManagerInviteCodes(SECRET_NAME, clock=SimClock(START))

    assert source.codes() == frozenset({"PILOTO-1", "PILOTO-2"})
    assert client.calls == [SECRET_NAME]


def test_the_cloud_source_accepts_one_code_per_line(monkeypatch):
    monkeypatch.setattr(
        "repaso.config.clients.secrets_client", lambda: StubSecrets("PILOTO-1\nPILOTO-2")
    )

    source = SecretsManagerInviteCodes(SECRET_NAME, clock=SimClock(START))

    assert source.codes() == frozenset({"PILOTO-1", "PILOTO-2"})


def test_the_cloud_source_reads_the_secret_once_per_ttl(monkeypatch):
    client = StubSecrets("PILOTO-1")
    monkeypatch.setattr("repaso.config.clients.secrets_client", lambda: client)
    clock = SimClock(START)
    source = SecretsManagerInviteCodes(SECRET_NAME, clock=clock)

    source.codes()
    clock.advance(minutes=int(CACHE_TTL_SECONDS // 60) - 1)
    source.codes()
    assert client.calls == [SECRET_NAME]

    clock.advance(minutes=2)
    source.codes()
    assert client.calls == [SECRET_NAME, SECRET_NAME]


def test_the_configured_value_overrides_the_secret(monkeypatch):
    client = StubSecrets("FROM-SECRET")
    monkeypatch.setattr("repaso.config.clients.secrets_client", lambda: client)

    source = SecretsManagerInviteCodes(SECRET_NAME, "FROM-SETTINGS", SimClock(START))

    assert source.codes() == frozenset({"FROM-SETTINGS"})
    assert client.calls == []


def test_the_cloud_source_says_so_when_no_client_exists(monkeypatch):
    monkeypatch.setattr("repaso.config.clients.secrets_client", lambda: None)

    with pytest.raises(RuntimeError):
        SecretsManagerInviteCodes(SECRET_NAME, clock=SimClock(START)).codes()


def test_a_cloud_source_without_a_secret_name_is_refused():
    with pytest.raises(ValueError):
        SecretsManagerInviteCodes("", clock=SimClock(START))


def test_the_builder_follows_the_mode(settings, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "repaso.config.clients.secrets_client", lambda: StubSecrets("FROM-SECRET")
    )

    assert isinstance(build_invite_codes(settings), LocalInviteCodes)
    cloud = build_invite_codes(cloud_settings(tmp_path))
    assert isinstance(cloud, SecretsManagerInviteCodes)
    assert cloud.codes() == frozenset({"FROM-SECRET"})
