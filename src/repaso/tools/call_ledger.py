import threading
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol, runtime_checkable
from uuid import uuid4

from pydantic import Field

from repaso.config.settings import Settings
from repaso.schemas.common import FrozenStrictModel
from repaso.tools.call_cost import CallCost
from repaso.tools.cassette import CassetteKind
from repaso.tools.model_usage import CallUsage

LEDGER_DIRNAME = "ledger"
LEDGER_FILENAME = "model_calls.jsonl"

_prompt_version: ContextVar[str | None] = ContextVar("repaso_prompt_version", default=None)


class LedgerFormatError(ValueError):
    pass


class CallOrigin(StrEnum):
    LIVE = "live"
    REPLAYED = "replayed"
    SIMULATED = "simulated"


class CallOutcome(StrEnum):
    OK = "ok"
    FAILED = "failed"
    DENIED = "denied"


class CallRecord(FrozenStrictModel):
    call_id: str = Field(min_length=1)
    at: datetime
    role: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    kind: CassetteKind
    output_model: str | None = None
    origin: CallOrigin
    outcome: CallOutcome
    latency_ms: float = Field(ge=0.0)
    usage: CallUsage | None = None
    cost: CallCost | None = None
    stop_reason: str | None = None
    retries: int = Field(default=0, ge=0)
    prompt_version: str | None = None
    error: str = ""

    @property
    def measured(self) -> bool:
        return self.origin is CallOrigin.LIVE


@runtime_checkable
class CallLedger(Protocol):
    def append(self, record: CallRecord) -> None: ...

    def records(self) -> list[CallRecord]: ...


class LocalCallLedger:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: CallRecord) -> None:
        line = record.model_dump_json()
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(f"{line}\n")

    def records(self) -> list[CallRecord]:
        return load_ledger(self.path) if self.path.exists() else []


class NullCallLedger:
    def append(self, record: CallRecord) -> None:
        return None

    def records(self) -> list[CallRecord]:
        return []


def load_ledger(path: Path) -> list[CallRecord]:
    if not path.exists():
        raise LedgerFormatError(f"ledger not found: {path}")
    records: list[CallRecord] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(CallRecord.model_validate_json(line))
        except ValueError as error:
            raise LedgerFormatError(f"{path}:{number}: {error}") from error
    return records


def ledger_path(settings: Settings) -> Path:
    if settings.call_ledger_path is not None:
        return settings.call_ledger_path
    return settings.local_data_dir / LEDGER_DIRNAME / LEDGER_FILENAME


def build_call_ledger(settings: Settings) -> CallLedger:
    return LocalCallLedger(ledger_path(settings))


def new_call_id() -> str:
    return uuid4().hex


@contextmanager
def declaring_prompt_version(version: str | None) -> Iterator[None]:
    token = _prompt_version.set(version)
    try:
        yield
    finally:
        _prompt_version.reset(token)


def declared_prompt_version() -> str | None:
    return _prompt_version.get()
