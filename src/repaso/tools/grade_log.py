import json
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


class LocalGradeLog:
    def __init__(self, root: Path) -> None:
        self.path = Path(root) / GRADES_FILENAME
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, result: GradeResult) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(result.model_dump_json() + "\n")

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

        stamp = result.graded_at.isoformat()
        item = {
            "pk": {"S": f"ITEM#{result.item_id}"},
            "sk": {"S": f"{GRADE_PREFIX}{result.student_id}#{stamp}"},
            "gsi1pk": {"S": f"STUDENT#{result.student_id}"},
            "gsi1sk": {"S": f"{GRADE_PREFIX}{stamp}"},
        } | _serialize(result)
        dynamodb_client().put_item(TableName=self._table, Item=item)

    def by_item(self, item_id: ItemId) -> list[GradeResult]:
        from repaso.config.clients import dynamodb_client

        found = dynamodb_client().query(
            TableName=self._table,
            KeyConditionExpression="pk = :pk AND begins_with(sk, :sk)",
            ExpressionAttributeValues={
                ":pk": {"S": f"ITEM#{item_id}"},
                ":sk": {"S": GRADE_PREFIX},
            },
        )
        return [_deserialize(item) for item in found.get("Items", [])]

    def by_student(self, student_id: StudentId) -> list[GradeResult]:
        from repaso.config.clients import dynamodb_client

        found = dynamodb_client().query(
            TableName=self._table,
            IndexName=INDEX_NAME,
            KeyConditionExpression="gsi1pk = :pk AND begins_with(gsi1sk, :sk)",
            ExpressionAttributeValues={
                ":pk": {"S": f"STUDENT#{student_id}"},
                ":sk": {"S": GRADE_PREFIX},
            },
        )
        return [_deserialize(item) for item in found.get("Items", [])]


def build_grade_log(settings: Settings) -> GradeLog:
    if settings.local_mode:
        return LocalGradeLog(settings.local_data_dir / STATE_DIRNAME)
    return DynamoGradeLog(settings.ddb_table)
