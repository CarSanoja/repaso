import os

import pytest

from repaso.config.clients import reset_client_cache
from repaso.config.settings import Settings, clear_settings_cache


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for key in list(os.environ):
        if key.startswith("REPASO_"):
            monkeypatch.delenv(key)
    clear_settings_cache()
    reset_client_cache()
    yield
    clear_settings_cache()
    reset_client_cache()


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(local_mode=True, local_data_dir=tmp_path / "local_data")
