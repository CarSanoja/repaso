from repaso.config.settings import Settings
from repaso.tools.guardrails import (
    DEFAULT_GUARDRAIL_VERSION,
    BedrockGuardrailsScreener,
    LocalScreener,
    Screener,
    build_screener,
)

CLIENT_PATH = "repaso.config.clients.bedrock_runtime_client"


class FakeGuardrailClient:
    def __init__(self, response: dict | None = None, error: Exception | None = None) -> None:
        self._response = response or {"action": "NONE"}
        self._error = error
        self.calls: list[dict] = []

    def apply_guardrail(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._response


def cloud_settings(tmp_path, **overrides) -> Settings:
    return Settings(
        aws_region="us-east-1", local_mode=False, local_data_dir=tmp_path, **overrides
    )


def install_client(monkeypatch, client: FakeGuardrailClient) -> FakeGuardrailClient:
    monkeypatch.setattr(CLIENT_PATH, lambda: client)
    return client


def test_bedrock_screener_satisfies_the_screener_protocol():
    assert isinstance(BedrockGuardrailsScreener("gr-1", "7"), Screener)
    assert Screener not in BedrockGuardrailsScreener.__mro__


def test_build_screener_returns_the_local_screener_in_local_mode(settings):
    assert isinstance(build_screener(settings), LocalScreener)


def test_build_screener_stays_local_in_the_cloud_without_a_guardrail_id(tmp_path):
    assert isinstance(build_screener(cloud_settings(tmp_path)), LocalScreener)


def test_build_screener_ignores_a_guardrail_id_in_local_mode(settings):
    assert isinstance(build_screener(settings, guardrail_id="gr-1"), LocalScreener)


def test_build_screener_returns_the_bedrock_screener_when_a_guardrail_id_is_given(tmp_path):
    screener = build_screener(cloud_settings(tmp_path), guardrail_id="gr-1", version="7")
    assert isinstance(screener, BedrockGuardrailsScreener)


def test_the_deployed_guardrail_reaches_the_screener_without_being_passed(monkeypatch, tmp_path):
    client = install_client(monkeypatch, FakeGuardrailClient())
    settings = cloud_settings(tmp_path, guardrail_id="gr-9", guardrail_version="4")

    build_screener(settings).screen("hola")

    assert client.calls[0]["guardrailIdentifier"] == "gr-9"
    assert client.calls[0]["guardrailVersion"] == "4"


def test_an_id_with_no_published_version_screens_against_the_draft(monkeypatch, tmp_path):
    client = install_client(monkeypatch, FakeGuardrailClient())

    build_screener(cloud_settings(tmp_path, guardrail_id="gr-9")).screen("hola")

    assert client.calls[0]["guardrailVersion"] == DEFAULT_GUARDRAIL_VERSION


def test_an_explicit_guardrail_wins_over_the_configured_one(monkeypatch, tmp_path):
    client = install_client(monkeypatch, FakeGuardrailClient())
    settings = cloud_settings(tmp_path, guardrail_id="gr-9", guardrail_version="4")

    build_screener(settings, guardrail_id="gr-1", version="7").screen("hola")

    assert client.calls[0]["guardrailIdentifier"] == "gr-1"
    assert client.calls[0]["guardrailVersion"] == "7"


def test_bedrock_screener_sends_the_guardrail_payload(monkeypatch, tmp_path):
    client = install_client(monkeypatch, FakeGuardrailClient())
    screener = build_screener(cloud_settings(tmp_path), guardrail_id="gr-1", version="7")
    verdict = screener.screen("hola")
    assert verdict.safe is True
    assert client.calls == [
        {
            "guardrailIdentifier": "gr-1",
            "guardrailVersion": "7",
            "source": "INPUT",
            "content": [{"text": {"text": "hola"}}],
        }
    ]


def test_intervention_maps_to_unsafe_with_the_assessment_names(monkeypatch):
    response = {
        "action": "GUARDRAIL_INTERVENED",
        "assessments": [{"topicPolicy": {}, "contentPolicy": {}}, {"topicPolicy": {}}],
    }
    install_client(monkeypatch, FakeGuardrailClient(response=response))
    verdict = BedrockGuardrailsScreener("gr-1", "7").screen("texto")
    assert verdict.safe is False
    assert verdict.reasons == ["topicPolicy", "contentPolicy"]


def test_intervention_without_assessments_still_carries_a_reason(monkeypatch):
    install_client(monkeypatch, FakeGuardrailClient(response={"action": "GUARDRAIL_INTERVENED"}))
    verdict = BedrockGuardrailsScreener("gr-1", "7").screen("texto")
    assert verdict.safe is False
    assert verdict.reasons == ["GUARDRAIL_INTERVENED"]


def test_a_raising_client_fails_closed(monkeypatch):
    install_client(monkeypatch, FakeGuardrailClient(error=RuntimeError("throttled")))
    verdict = BedrockGuardrailsScreener("gr-1", "7").screen("texto")
    assert verdict.safe is False
    assert verdict.reasons == ["screener_error"]


def test_a_missing_client_fails_closed(monkeypatch):
    monkeypatch.setattr(CLIENT_PATH, lambda: None)
    assert BedrockGuardrailsScreener("gr-1", "7").screen("texto").safe is False


def test_a_malformed_response_fails_closed(monkeypatch):
    response = {"action": "GUARDRAIL_INTERVENED", "assessments": 7}
    install_client(monkeypatch, FakeGuardrailClient(response=response))
    verdict = BedrockGuardrailsScreener("gr-1", "7").screen("texto")
    assert verdict.safe is False
    assert verdict.reasons == ["screener_error"]


def test_bedrock_screener_redacts_like_the_local_screener(monkeypatch):
    install_client(monkeypatch, FakeGuardrailClient())
    text = "Escribe a ana@colegio.edu.ve o al 0412-555-1234"
    assert BedrockGuardrailsScreener("gr-1", "7").redact(text) == LocalScreener().redact(text)
