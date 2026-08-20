import re
from typing import Any, Protocol, runtime_checkable

from repaso.config.settings import Settings
from repaso.schemas.common import FrozenStrictModel

INJECTION_MARKERS: tuple[str, ...] = (
    "ignore your",
    "ignore all previous",
    "system:",
    "developer:",
    "you are now",
    "disregard",
    "reveal your",
    "award full marks",
    "skip all practice",
    "act as",
)

MARKER_REASON_PREFIX = "injection_marker:"
SCREENER_ERROR_REASON = "screener_error"
GUARDRAIL_INTERVENED = "GUARDRAIL_INTERVENED"
DEFAULT_GUARDRAIL_VERSION = "DRAFT"
REDACTION = "[redacted]"

EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
NATIONAL_ID_PATTERN = re.compile(r"\b[VEJGPvejgp][-.\s]?\d{6,9}\b")
PHONE_PATTERN = re.compile(r"\+?\d(?:[ -]?\d){6,}")


class ScreenVerdict(FrozenStrictModel):
    safe: bool
    reasons: list[str] = []


@runtime_checkable
class Screener(Protocol):
    def screen(self, text: str) -> ScreenVerdict: ...

    def redact(self, text: str) -> str: ...


def _redact_text(text: str) -> str:
    redacted = EMAIL_PATTERN.sub(REDACTION, text)
    redacted = NATIONAL_ID_PATTERN.sub(REDACTION, redacted)
    return PHONE_PATTERN.sub(REDACTION, redacted)


def _injection_reasons(text: str, markers: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    return [f"{MARKER_REASON_PREFIX}{marker}" for marker in markers if marker in lowered]


def _assessment_names(response: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for assessment in response.get("assessments") or []:
        for name in assessment:
            if name not in names:
                names.append(name)
    return names


def _verdict_from_response(response: dict[str, Any]) -> ScreenVerdict:
    if response.get("action") != GUARDRAIL_INTERVENED:
        return ScreenVerdict(safe=True)
    return ScreenVerdict(safe=False, reasons=_assessment_names(response) or [GUARDRAIL_INTERVENED])


class LocalScreener:
    def __init__(self, markers: tuple[str, ...] = INJECTION_MARKERS) -> None:
        self._markers = markers

    def screen(self, text: str) -> ScreenVerdict:
        reasons = _injection_reasons(text, self._markers)
        return ScreenVerdict(safe=not reasons, reasons=reasons)

    def redact(self, text: str) -> str:
        return _redact_text(text)


class BedrockGuardrailsScreener:
    def __init__(self, guardrail_id: str, version: str = DEFAULT_GUARDRAIL_VERSION) -> None:
        self._guardrail_id = guardrail_id
        self._version = version

    def screen(self, text: str) -> ScreenVerdict:
        try:
            from repaso.config.clients import bedrock_runtime_client

            response = bedrock_runtime_client().apply_guardrail(
                guardrailIdentifier=self._guardrail_id,
                guardrailVersion=self._version,
                source="INPUT",
                content=[{"text": {"text": text}}],
            )
            return _verdict_from_response(response)
        except Exception:
            return ScreenVerdict(safe=False, reasons=[SCREENER_ERROR_REASON])

    def redact(self, text: str) -> str:
        return _redact_text(text)


def build_screener(
    settings: Settings,
    *,
    guardrail_id: str | None = None,
    version: str = DEFAULT_GUARDRAIL_VERSION,
) -> Screener:
    if settings.local_mode:
        return LocalScreener()
    if guardrail_id:
        return BedrockGuardrailsScreener(guardrail_id, version)
    return LocalScreener()
