import sys
from types import ModuleType

import pytest

from repaso.runtime.app import agentcore_entrypoint, build_runtime_app
from tests.orchestration.fixtures import make_services
from tests.runtime.fixtures import request


class FakeAgentCoreApp:
    def __init__(self) -> None:
        self.handler = None
        self.started = False

    def entrypoint(self, handler):
        self.handler = handler
        return handler

    def run(self) -> None:
        self.started = True


@pytest.fixture
def fake_agentcore(monkeypatch):
    package = ModuleType("bedrock_agentcore")
    runtime = ModuleType("bedrock_agentcore.runtime")
    runtime.BedrockAgentCoreApp = FakeAgentCoreApp
    package.runtime = runtime
    monkeypatch.setitem(sys.modules, "bedrock_agentcore", package)
    monkeypatch.setitem(sys.modules, "bedrock_agentcore.runtime", runtime)
    return runtime


def test_the_agentcore_sdk_is_only_imported_when_the_app_is_built():
    assert "bedrock_agentcore" not in sys.modules


def test_building_the_app_registers_the_invocation_entrypoint(fake_agentcore):
    app = build_runtime_app()

    assert isinstance(app, FakeAgentCoreApp)
    assert app.handler is agentcore_entrypoint


async def test_the_registered_entrypoint_answers_with_a_structured_result(
    fake_agentcore, settings, monkeypatch
):
    services = make_services(settings)
    monkeypatch.setattr("repaso.runtime.entrypoint.runtime_services", lambda: services)
    app = build_runtime_app()

    response = await app.handler(request("daily_close"), None)

    assert response["ok"] is True
    assert response["kind"] == "daily_close"
