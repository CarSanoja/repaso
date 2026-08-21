import json
from pathlib import Path
from typing import Protocol, runtime_checkable

KEY_SEPARATOR = "#"
UPDATE_KEY_PREFIX = "update"
JOB_KEY_PREFIX = "job"


def _join_key(parts: tuple[str, ...]) -> str:
    for part in parts:
        if not part:
            raise ValueError("key parts must be non-empty")
        if KEY_SEPARATOR in part:
            raise ValueError(f"key parts must not contain {KEY_SEPARATOR!r}")
    return KEY_SEPARATOR.join(parts)


def update_key(chat_ref: str, update_id: int | str) -> str:
    return _join_key((UPDATE_KEY_PREFIX, chat_ref, str(update_id)))


def job_key(kind: str, subject: str, occurred_on: str) -> str:
    return _join_key((JOB_KEY_PREFIX, kind, subject, occurred_on))


@runtime_checkable
class ClaimLedger(Protocol):
    def claim(self, key: str, owner: str) -> bool: ...

    def owner_of(self, key: str) -> str | None: ...

    def release(self, key: str) -> None: ...


class LocalClaimLedger:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self._owners: dict[str, str] = {}
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._replay(path)

    def claim(self, key: str, owner: str) -> bool:
        if key in self._owners:
            return False
        self._owners[key] = owner
        self._append(key, owner)
        return True

    def owner_of(self, key: str) -> str | None:
        return self._owners.get(key)

    def release(self, key: str) -> None:
        self._owners.pop(key, None)

    def _replay(self, path: Path) -> None:
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            self._owners[record["key"]] = record["owner"]

    def _append(self, key: str, owner: str) -> None:
        if self._path is None:
            return
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"key": key, "owner": owner}, sort_keys=True) + "\n")


def claim_or_skip(ledger: ClaimLedger, key: str, owner: str) -> bool:
    return ledger.claim(key, owner)
