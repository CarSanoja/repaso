import ast
from pathlib import Path

import pytest

import repaso.core
import repaso.runtime
from repaso.config.models import ModelRole
from repaso.config.settings import Settings
from repaso.core.harness.clock import SystemClock
from repaso.runtime.context import (
    build_runtime_services,
    reset_runtime_session,
    runtime_services,
)
from repaso.tools.instrumented_model import InstrumentedModel
from repaso.tools.llm import LocalPlaybackModel
from repaso.tools.state_local import LocalStateStore
from repaso.tools.telegram import LocalOutbox

CLOUD_MODULES = ("boto3", "botocore", "bedrock_agentcore", "strands.models.bedrock")


@pytest.fixture(autouse=True)
def clean_session():
    reset_runtime_session()
    yield
    reset_runtime_session()


def module_level_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def python_files(package) -> list[Path]:
    return sorted(Path(package.__path__[0]).rglob("*.py"))


def test_local_mode_wires_every_service_to_its_local_implementation(settings):
    services = build_runtime_services(settings)

    assert isinstance(services.clock, SystemClock)
    assert isinstance(services.store, LocalStateStore)
    assert isinstance(services.sender, LocalOutbox)
    assert set(services.models) == set(ModelRole)
    for model in services.models.values():
        assert isinstance(model, InstrumentedModel)
        assert isinstance(model.inner, LocalPlaybackModel)


def test_services_are_reused_across_invocations_and_rebuilt_on_new_settings(settings):
    first = runtime_services(settings)

    assert runtime_services(settings) is first

    other = Settings(local_mode=True, local_data_dir=settings.local_data_dir / "other")
    assert runtime_services(other) is not first


def test_resetting_the_session_forces_a_rebuild(settings):
    first = runtime_services(settings)
    reset_runtime_session()

    assert runtime_services(settings) is not first


@pytest.mark.parametrize("path", python_files(repaso.runtime), ids=lambda path: path.name)
def test_the_glue_layer_imports_no_cloud_sdk_at_module_level(path):
    imported = module_level_imports(path)

    assert [name for name in imported if name.startswith(CLOUD_MODULES)] == []


@pytest.mark.parametrize("path", python_files(repaso.core), ids=lambda path: path.name)
def test_the_core_never_learns_about_agentcore_or_the_glue(path):
    imported = module_level_imports(path)

    assert [name for name in imported if name.startswith(("bedrock_agentcore",))] == []
    assert [name for name in imported if name.startswith("repaso.runtime")] == []
