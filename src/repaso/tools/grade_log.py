import fcntl
import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from repaso.config.settings import Settings
from repaso.core.harness.clock import Clock, SystemClock
from repaso.core.harness.retention import TTL_ATTRIBUTE
from repaso.schemas.common import ItemId, StudentId
from repaso.schemas.grading import GradeResult
from repaso.tools.grade_words import (
    WORDS_FILENAME,
    WORDS_PREFIX,
    ChildWords,
    attempt_only,
    rejoin,
    stamp_of,
    still_said,
    words_of,
)

GRADES_FILENAME = "grades.jsonl"
STATE_DIRNAME = "state"
INDEX_NAME = "gsi1"
GRADE_PREFIX = "GRADE#"


@runtime_checkable
class GradeLog(Protocol):
    def append(self, result: GradeResult) -> None: ...
    def by_item(self, item_id: ItemId) -> list[GradeResult]: ...
    def by_student(self, student_id: StudentId) -> list[GradeResult]: ...
    def forget_student(self, student_id: StudentId) -> None: ...


class LocalGradeLog:
    def __init__(self, root: Path, clock: Clock | None = None) -> None:
        self.path = Path(root) / GRADES_FILENAME
        self.words_path = Path(root) / WORDS_FILENAME
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock or SystemClock()

    def append(self, result: GradeResult) -> None:
        with self.path.with_suffix(".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if result.id and any(row.id == result.id for row in self._read()):
                return
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(attempt_only(result).model_dump_json() + "\n")
            words = words_of(result)
            if words is not None:
                with self.words_path.open("a", encoding="utf-8") as handle:
                    handle.write(words.model_dump_json() + "\n")

    def forget_student(self, student_id: StudentId) -> None:
        with self.path.with_suffix(".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            kept = [r for r in self._read() if r.student_id != student_id]
            temp = self.path.with_suffix(".tmp")
            temp.write_text("".join(r.model_dump_json() + "\n" for r in kept))
            os.replace(temp, self.path)
            self._forget_words(student_id)

    def by_item(self, item_id: ItemId) -> list[GradeResult]:
        return [result for result in self._read() if result.item_id == item_id]

    def by_student(self, student_id: StudentId) -> list[GradeResult]:
        found = [result for result in self._read() if result.student_id == student_id]
        return rejoin(found, still_said(self._words(), self._clock.now()))

    def _read(self) -> list[GradeResult]:
        return [GradeResult.model_validate_json(line) for line in self._lines(self.path)]

    def _words(self) -> list[ChildWords]:
        return [ChildWords.model_validate_json(line) for line in self._lines(self.words_path)]

    def _forget_words(self, student_id: StudentId) -> None:
        kept = [row for row in self._words() if not row.key.startswith(f"{student_id}#")]
        temp = self.words_path.with_suffix(".tmp")
        temp.write_text("".join(row.model_dump_json() + "\n" for row in kept))
        os.replace(temp, self.words_path)

    @staticmethod
    def _lines(path: Path) -> list[str]:
        if not path.exists():
            return []
        return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _serialize(model: BaseModel) -> dict[str, Any]:
    from boto3.dynamodb.types import TypeSerializer

    doc = json.loads(model.model_dump_json(), parse_float=Decimal)
    return {"doc": TypeSerializer().serialize(doc)}


def _deserialize(item: dict[str, Any]) -> GradeResult:
    from boto3.dynamodb.types import TypeDeserializer

    return GradeResult.model_validate(TypeDeserializer().deserialize(item["doc"]))


def _deserialize_words(item: dict[str, Any]) -> ChildWords:
    from boto3.dynamodb.types import TypeDeserializer

    return ChildWords.model_validate(TypeDeserializer().deserialize(item["doc"]))


def _owned_by(row: dict[str, Any], student_id: StudentId) -> bool:
    if "doc" not in row:
        return False
    key = row["sk"]["S"]
    if key.startswith(GRADE_PREFIX):
        return _deserialize(row).student_id == student_id
    if key.startswith(WORDS_PREFIX):
        return _deserialize_words(row).key.startswith(f"{student_id}#")
    return False


class DynamoGradeLog:
    def __init__(self, table: str, clock: Clock | None = None) -> None:
        self._table = table
        self._clock = clock or SystemClock()

    def append(self, result: GradeResult) -> None:
        from repaso.config.clients import dynamodb_client

        stamp = stamp_of(result)
        attempt = attempt_only(result)
        item = {
            "pk": {"S": f"ITEM#{result.item_id}"},
            "sk": {"S": f"{GRADE_PREFIX}{result.student_id}#{stamp}"},
            "gsi1pk": {"S": f"STUDENT#{result.student_id}"},
            "gsi1sk": {"S": f"{GRADE_PREFIX}{stamp}"},
        } | _serialize(attempt)
        # A strongly consistent family deletion must not depend on a GSI catching up.
        mirror = item | {
            "pk": {"S": f"STUDENT#{result.student_id}"},
            "sk": {"S": f"GRADE#{result.item_id}#{stamp}"},
        }
        mirror.pop("gsi1pk", None)
        mirror.pop("gsi1sk", None)
        writes = [
            {"Put": {"TableName": self._table, "Item": item}},
            {"Put": {"TableName": self._table, "Item": mirror}},
        ]
        said = self._words_row(result, stamp)
        if said is not None:
            writes.append({"Put": {"TableName": self._table, "Item": said}})
        dynamodb_client().transact_write_items(TransactItems=writes)

    def _words_row(self, result: GradeResult, stamp: str) -> dict[str, Any] | None:
        words = words_of(result)
        if words is None:
            return None
        return {
            "pk": {"S": f"STUDENT#{result.student_id}"},
            "sk": {"S": f"{WORDS_PREFIX}{result.item_id}#{stamp}"},
            TTL_ATTRIBUTE: {"N": str(words.expires_at)},
        } | _serialize(words)

    def forget_student(self, student_id: StudentId) -> None:
        from repaso.config.clients import dynamodb_client
        from repaso.tools.state_dynamo_io import delete_row

        # Includes older rows written before the primary student mirror existed.
        client = dynamodb_client()
        request = {"TableName": self._table, "ConsistentRead": True}
        keys = []
        while True:
            page = client.scan(**request)
            for row in page.get("Items", []):
                if _owned_by(row, student_id):
                    keys.append((row["pk"]["S"], row["sk"]["S"]))
            if not page.get("LastEvaluatedKey"):
                break
            request["ExclusiveStartKey"] = page["LastEvaluatedKey"]
        for pk, sk in keys:
            delete_row(self._table, pk, sk)

    def by_item(self, item_id: ItemId) -> list[GradeResult]:

        from repaso.tools.state_dynamo_io import query_all

        found = query_all(
            TableName=self._table,
            KeyConditionExpression="pk = :pk AND begins_with(sk, :sk)",
            ExpressionAttributeValues={
                ":pk": {"S": f"ITEM#{item_id}"},
                ":sk": {"S": GRADE_PREFIX},
            },
        )
        return [_deserialize(item) for item in found]

    def by_student(self, student_id: StudentId) -> list[GradeResult]:
        from repaso.tools.state_dynamo_io import query_all, query_prefix

        primary = query_prefix(self._table, f"STUDENT#{student_id}", GRADE_PREFIX, GradeResult)
        # Older deployments wrote only the GSI. Keep their history readable;
        # every new result is also present in the strongly consistent primary.
        legacy = [
            _deserialize(row)
            for row in query_all(
                TableName=self._table,
                IndexName=INDEX_NAME,
                KeyConditionExpression="gsi1pk = :pk AND begins_with(gsi1sk, :sk)",
                ExpressionAttributeValues={
                    ":pk": {"S": f"STUDENT#{student_id}"},
                    ":sk": {"S": GRADE_PREFIX},
                },
            )
        ]
        merged = {(g.item_id, g.id or g.graded_at.isoformat()): g for g in legacy + primary}
        attempts = sorted(merged.values(), key=lambda g: (g.graded_at, g.id or ""))
        return rejoin(attempts, still_said(self._said(student_id), self._clock.now()))

    def _said(self, student_id: StudentId) -> list[ChildWords]:
        from repaso.tools.state_dynamo_io import query_prefix

        return query_prefix(self._table, f"STUDENT#{student_id}", WORDS_PREFIX, ChildWords)


def effective_grades(grades: list[GradeResult], final_only: bool = False) -> list[GradeResult]:
    superseded = {g.supersedes for g in grades if g.supersedes}
    kept = [
        g
        for g in grades
        if g.id not in superseded
        and (not final_only or (g.correct is not None and not g.quarantined))
    ]
    return sorted(kept, key=lambda g: (g.responded_at or g.graded_at, g.graded_at))


def build_grade_log(settings: Settings, clock: Clock | None = None) -> GradeLog:
    if settings.local_mode:
        return LocalGradeLog(settings.local_data_dir / STATE_DIRNAME, clock)
    return DynamoGradeLog(settings.ddb_table, clock)
