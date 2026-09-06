import fcntl
import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from repaso.config.settings import Settings
from repaso.schemas.common import ItemId, StudentId
from repaso.schemas.grading import GradeResult

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
    def __init__(self, root: Path) -> None:
        self.path = Path(root) / GRADES_FILENAME
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, result: GradeResult) -> None:
        with self.path.with_suffix(".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if result.id and any(row.id == result.id for row in self._read()):
                return
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(result.model_dump_json() + "\n")

    def forget_student(self, student_id: StudentId) -> None:
        with self.path.with_suffix(".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            kept = [r for r in self._read() if r.student_id != student_id]
            temp = self.path.with_suffix(".tmp")
            temp.write_text("".join(r.model_dump_json() + "\n" for r in kept))
            os.replace(temp, self.path)

    def by_item(self, item_id: ItemId) -> list[GradeResult]:
        return [result for result in self._read() if result.item_id == item_id]

    def by_student(self, student_id: StudentId) -> list[GradeResult]:
        return [result for result in self._read() if result.student_id == student_id]

    def _read(self) -> list[GradeResult]:
        if not self.path.exists():
            return []
        return [
            GradeResult.model_validate_json(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]


def _serialize(model: BaseModel) -> dict[str, Any]:
    from boto3.dynamodb.types import TypeSerializer

    doc = json.loads(model.model_dump_json(), parse_float=Decimal)
    return {"doc": TypeSerializer().serialize(doc)}


def _deserialize(item: dict[str, Any]) -> GradeResult:
    from boto3.dynamodb.types import TypeDeserializer

    return GradeResult.model_validate(TypeDeserializer().deserialize(item["doc"]))


class DynamoGradeLog:
    def __init__(self, table: str) -> None:
        self._table = table

    def append(self, result: GradeResult) -> None:
        from repaso.config.clients import dynamodb_client

        stamp = result.id or result.graded_at.isoformat()
        item = {
            "pk": {"S": f"ITEM#{result.item_id}"},
            "sk": {"S": f"{GRADE_PREFIX}{result.student_id}#{stamp}"},
            "gsi1pk": {"S": f"STUDENT#{result.student_id}"},
            "gsi1sk": {"S": f"{GRADE_PREFIX}{stamp}"},
        } | _serialize(result)
        # A strongly consistent family deletion must not depend on a GSI catching up.
        mirror = item | {
            "pk": {"S": f"STUDENT#{result.student_id}"},
            "sk": {"S": f"GRADE#{result.item_id}#{stamp}"},
        }
        mirror.pop("gsi1pk", None)
        mirror.pop("gsi1sk", None)
        dynamodb_client().transact_write_items(
            TransactItems=[
                {"Put": {"TableName": self._table, "Item": item}},
                {"Put": {"TableName": self._table, "Item": mirror}},
            ]
        )

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
                if row["sk"]["S"].startswith("GRADE#") and "doc" in row:
                    if _deserialize(row).student_id == student_id:
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
        return sorted(merged.values(), key=lambda g: (g.graded_at, g.id or ""))


def effective_grades(grades: list[GradeResult], final_only: bool = False) -> list[GradeResult]:
    superseded = {g.supersedes for g in grades if g.supersedes}
    kept = [
        g
        for g in grades
        if g.id not in superseded
        and (not final_only or (g.correct is not None and not g.quarantined))
    ]
    return sorted(kept, key=lambda g: (g.responded_at or g.graded_at, g.graded_at))


def build_grade_log(settings: Settings) -> GradeLog:
    if settings.local_mode:
        return LocalGradeLog(settings.local_data_dir / STATE_DIRNAME)
    return DynamoGradeLog(settings.ddb_table)
