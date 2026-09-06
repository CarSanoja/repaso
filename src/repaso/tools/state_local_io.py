import json
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class JsonTables:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._lock = threading.RLock()
        self._root.mkdir(parents=True, exist_ok=True)
        with self.exclusive():
            self.recover()

    @contextmanager
    def exclusive(self):
        import fcntl

        with self._lock, (self._root / ".write.lock").open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def recover(self) -> None:
        journal = self._root / "transaction.json"
        if journal.exists():
            for table, rows in json.loads(journal.read_text()).items():
                self.write(table, rows)
            journal.unlink()

    def transaction(self, tables: dict[str, dict]) -> None:
        # Caller holds exclusive(); a fresh process finishes interrupted writes.
        self.write("transaction", tables)
        self.recover()

    def read(self, table: str) -> dict[str, Any]:
        path = self._root / f"{table}.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def write(self, table: str, rows: dict[str, Any]) -> None:
        path = self._root / f"{table}.json"
        temp = path.with_name(f"{table}.{os.getpid()}.tmp")
        temp.write_text(json.dumps(rows, sort_keys=True), encoding="utf-8")
        os.replace(temp, path)

    def put(self, table: str, key: str, model: BaseModel) -> None:
        with self.exclusive():
            self.recover()
            rows = self.read(table)
            rows[key] = model.model_dump(mode="json")
            self.write(table, rows)

    def delete(self, table: str, key: str) -> None:
        with self.exclusive():
            self.recover()
            rows = self.read(table)
            if key in rows:
                del rows[key]
                self.write(table, rows)

    def get[M: BaseModel](self, table: str, key: str, model: type[M]) -> M | None:
        row = self.read(table).get(key)
        return model.model_validate(row) if row is not None else None

    def all[M: BaseModel](self, table: str, model: type[M]) -> list[M]:
        return [model.model_validate(row) for row in self.read(table).values()]

    def where[M: BaseModel](self, table: str, model: type[M], **fields: Any) -> list[M]:
        rows = self.all(table, model)
        return [row for row in rows if all(getattr(row, k) == v for k, v in fields.items())]

    def delete_where[M: BaseModel](self, table: str, model: type[M], **fields: Any) -> None:
        with self.exclusive():
            self.recover()
            rows = self.read(table)
            kept = {
                key: row
                for key, row in rows.items()
                if not all(getattr(model.model_validate(row), k) == v for k, v in fields.items())
            }
            if len(kept) != len(rows):
                self.write(table, kept)

    def claim(self, table: str, key: str, owner: str) -> bool:
        with self.exclusive():
            self.recover()
            claims = self.read(table)
            if key in claims:
                return False
            claims[key] = owner
            self.write(table, claims)
            return True
