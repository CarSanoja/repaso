from typing import Any, Protocol, runtime_checkable

from pydantic import Field

from repaso.config.settings import Settings
from repaso.schemas.channel import MediaKind
from repaso.schemas.common import FrozenStrictModel

DECODED_TEXT_CONFIDENCE = 0.99
TEXTRACT_CONFIDENCE_SCALE = 100.0
LINE_BLOCK = "LINE"


class ExtractResult(FrozenStrictModel):
    text: str
    confidence: float = Field(ge=0.0, le=1.0)


@runtime_checkable
class TextExtractor(Protocol):
    def extract(self, data: bytes, kind: MediaKind) -> ExtractResult: ...


class LocalTextExtractor:
    def extract(self, data: bytes, kind: MediaKind) -> ExtractResult:
        try:
            decoded = data.decode("utf-8")
        except UnicodeDecodeError:
            return ExtractResult(text="", confidence=0.0)
        text = decoded.strip()
        if not text:
            return ExtractResult(text="", confidence=0.0)
        return ExtractResult(text=text, confidence=DECODED_TEXT_CONFIDENCE)


class TextractExtractor:
    def extract(self, data: bytes, kind: MediaKind) -> ExtractResult:
        from repaso.config.clients import textract_client

        client = textract_client()
        if client is None:
            raise RuntimeError("textract client is unavailable in local mode")
        response = client.detect_document_text(Document={"Bytes": data})
        return _result_from_blocks(response.get("Blocks", []))


def _result_from_blocks(blocks: list[dict[str, Any]]) -> ExtractResult:
    lines = [block for block in blocks if block.get("BlockType") == LINE_BLOCK]
    if not lines:
        return ExtractResult(text="", confidence=0.0)
    text = "\n".join(str(block.get("Text", "")) for block in lines)
    total = sum(float(block.get("Confidence", 0.0)) for block in lines)
    confidence = total / len(lines) / TEXTRACT_CONFIDENCE_SCALE
    return ExtractResult(text=text, confidence=min(1.0, max(0.0, confidence)))


def build_text_extractor(settings: Settings) -> TextExtractor:
    if settings.local_mode:
        return LocalTextExtractor()
    return TextractExtractor()
