import json
import threading
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from repaso.tools.model_usage import CallUsage

STREAM_KIND = "stream"
STRUCTURED_KIND = "structured_output"

CassetteKind = Literal["structured_output", "stream"]


class CassetteFormatError(ValueError):
    pass


class CassetteEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(min_length=1)
    kind: CassetteKind
    output_model: str | None = None
    payload: dict[str, Any] | None = None
    text: str | None = None
    reasoning: str | None = None
    model_id: str | None = None
    stop_reason: str | None = None
    usage: CallUsage | None = None
    latency_ms: float | None = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def entry_carries_what_its_kind_needs(self) -> "CassetteEntry":
        if self.kind == STRUCTURED_KIND and (self.output_model is None or self.payload is None):
            raise ValueError("a structured_output entry needs both output_model and payload")
        if self.kind == STREAM_KIND and self.text is None:
            raise ValueError("a stream entry needs text")
        return self


def load_cassette(path: Path) -> list[CassetteEntry]:
    if not path.exists():
        raise CassetteFormatError(f"cassette not found: {path}")
    entries: list[CassetteEntry] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entries.append(CassetteEntry.model_validate_json(line))
        except ValueError as error:
            raise CassetteFormatError(f"{path}:{number}: {error}") from error
    return entries


class CassetteWriter:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def append(self, entry: CassetteEntry) -> None:
        line = json.dumps(entry.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
        with self._lock, self._path.open("a", encoding="utf-8") as handle:
            handle.write(f"{line}\n")
