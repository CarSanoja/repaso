import json
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from repaso.config.clients import dynamodb_client
from repaso.schemas.common import (
    CompetencyId,
    EscalationId,
    FamilyId,
    ItemId,
    MaterialId,
    SessionId,
    StudentId,
)
from repaso.schemas.escalation import Escalation, EscalationStatus
from repaso.schemas.family import Family
from repaso.schemas.item import Item, ItemStatus
from repaso.schemas.mastery import MasteryState
from repaso.schemas.material import Material
from repaso.schemas.review import QuarantineItem, QuarantineStatus
from repaso.schemas.schedule import SpacedItemState
from repaso.schemas.session import PracticeSession
from repaso.schemas.student import Student

INDEX_NAME = "gsi1"


def _key(pk: str, sk: str) -> dict[str, Any]:
    return {"pk": {"S": pk}, "sk": {"S": sk}}


def _serialize(model: BaseModel) -> dict[str, Any]:
    from boto3.dynamodb.types import TypeSerializer

    doc = json.loads(model.model_dump_json(), parse_float=Decimal)
    return {"doc": TypeSerializer().serialize(doc)}


def _deserialize[M: BaseModel](item: dict[str, Any], model: type[M]) -> M:
    from boto3.dynamodb.types import TypeDeserializer

    return model.model_validate(TypeDeserializer().deserialize(item["doc"]))


class DynamoStateStore:
    def __init__(self, table: str) -> None:
        self._table = table

    def put_family(self, family: Family) -> None:
        self._put(f"FAMILY#{family.id}", "PROFILE", family)
        lookup = _key(f"CHAT#{family.channel}#{family.chat_ref}", "FAMILY")
        dynamodb_client().put_item(TableName=self._table, Item=lookup | {"ref": {"S": family.id}})

    def get_family(self, family_id: FamilyId) -> Family | None:
        return self._get(f"FAMILY#{family_id}", "PROFILE", Family)

    def find_family_by_chat(self, channel: str, chat_ref: str) -> Family | None:
        found = dynamodb_client().get_item(
            TableName=self._table, Key=_key(f"CHAT#{channel}#{chat_ref}", "FAMILY")
        )
        item = found.get("Item")
        return self.get_family(FamilyId(item["ref"]["S"])) if item else None

    def put_student(self, student: Student) -> None:
        self._put(f"FAMILY#{student.family_id}", f"STUDENT#{student.id}", student)
        self._put(f"STUDENT#{student.id}", "PROFILE", student)

    def get_student(self, student_id: StudentId) -> Student | None:
        return self._get(f"STUDENT#{student_id}", "PROFILE", Student)

    def list_students(self, family_id: FamilyId) -> list[Student]:
        return self._query(f"FAMILY#{family_id}", "STUDENT#", Student)

    def put_mastery(self, state: MasteryState) -> None:
        self._put(f"STUDENT#{state.student_id}", f"MASTERY#{state.competency_id}", state)

    def get_mastery(
        self, student_id: StudentId, competency_id: CompetencyId
    ) -> MasteryState | None:
        return self._get(f"STUDENT#{student_id}", f"MASTERY#{competency_id}", MasteryState)

    def list_mastery(self, student_id: StudentId) -> list[MasteryState]:
        return self._query(f"STUDENT#{student_id}", "MASTERY#", MasteryState)

    def put_spaced(self, state: SpacedItemState) -> None:
        self._put(f"STUDENT#{state.student_id}", f"SPACED#{state.item_id}", state)

    def list_spaced(self, student_id: StudentId) -> list[SpacedItemState]:
        return self._query(f"STUDENT#{student_id}", "SPACED#", SpacedItemState)

    def put_item(self, item: Item) -> None:
        gsi1 = (f"COMP#{item.competency_id}", f"ITEM#{item.id}")
        self._put(f"ITEM#{item.id}", "PROFILE", item, gsi1)

    def get_item(self, item_id: ItemId) -> Item | None:
        return self._get(f"ITEM#{item_id}", "PROFILE", Item)

    def list_items_by_competency(
        self, competency_id: CompetencyId, status: ItemStatus | None = None
    ) -> list[Item]:
        found = self._query_index(f"COMP#{competency_id}", Item)
        return found if status is None else [item for item in found if item.status is status]

    def put_material(self, material: Material) -> None:
        self._put(f"MATERIAL#{material.id}", "PROFILE", material)

    def get_material(self, material_id: MaterialId) -> Material | None:
        return self._get(f"MATERIAL#{material_id}", "PROFILE", Material)

    def put_session(self, session: PracticeSession) -> None:
        self._put(f"STUDENT#{session.student_id}", f"SESSION#{session.session_date}", session)
        self._put(f"SESSION#{session.id}", "PROFILE", session)

    def get_session(self, session_id: SessionId) -> PracticeSession | None:
        return self._get(f"SESSION#{session_id}", "PROFILE", PracticeSession)

    def get_session_by_date(
        self, student_id: StudentId, session_date: date
    ) -> PracticeSession | None:
        return self._get(f"STUDENT#{student_id}", f"SESSION#{session_date}", PracticeSession)

    def put_escalation(self, escalation: Escalation) -> None:
        pending = escalation.status is EscalationStatus.PENDING
        gsi1 = (f"ESCPENDING#{escalation.family_id}", f"ESC#{escalation.id}") if pending else None
        self._put(f"FAMILY#{escalation.family_id}", f"ESC#{escalation.id}", escalation, gsi1)
        self._put(f"ESC#{escalation.id}", "PROFILE", escalation)

    def get_escalation(self, escalation_id: EscalationId) -> Escalation | None:
        return self._get(f"ESC#{escalation_id}", "PROFILE", Escalation)

    def list_pending_escalations(self, family_id: FamilyId) -> list[Escalation]:
        return self._query_index(f"ESCPENDING#{family_id}", Escalation)

    def put_quarantine(self, item: QuarantineItem) -> None:
        self._put(f"FAMILY#{item.family_id}", f"QUAR#{item.id}", item)

    def list_pending_quarantine(self, family_id: FamilyId) -> list[QuarantineItem]:
        found = self._query(f"FAMILY#{family_id}", "QUAR#", QuarantineItem)
        return [item for item in found if item.status is QuarantineStatus.PENDING]

    def claim(self, key: str, owner: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            dynamodb_client().put_item(
                TableName=self._table,
                Item=_key(f"CLAIM#{key}", "CLAIM") | {"owner": {"S": owner}},
                ConditionExpression="attribute_not_exists(pk)",
            )
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise
        return True

    def _put(
        self, pk: str, sk: str, model: BaseModel, gsi1: tuple[str, str] | None = None
    ) -> None:
        item = _key(pk, sk) | _serialize(model)
        if gsi1 is not None:
            item["gsi1pk"] = {"S": gsi1[0]}
            item["gsi1sk"] = {"S": gsi1[1]}
        dynamodb_client().put_item(TableName=self._table, Item=item)

    def _get[M: BaseModel](self, pk: str, sk: str, model: type[M]) -> M | None:
        found = dynamodb_client().get_item(TableName=self._table, Key=_key(pk, sk))
        item = found.get("Item")
        return _deserialize(item, model) if item else None

    def _query[M: BaseModel](self, pk: str, prefix: str, model: type[M]) -> list[M]:
        found = dynamodb_client().query(
            TableName=self._table,
            KeyConditionExpression="pk = :pk AND begins_with(sk, :sk)",
            ExpressionAttributeValues={":pk": {"S": pk}, ":sk": {"S": prefix}},
        )
        return [_deserialize(item, model) for item in found.get("Items", [])]

    def _query_index[M: BaseModel](self, gsi1pk: str, model: type[M]) -> list[M]:
        found = dynamodb_client().query(
            TableName=self._table,
            IndexName=INDEX_NAME,
            KeyConditionExpression="gsi1pk = :pk",
            ExpressionAttributeValues={":pk": {"S": gsi1pk}},
        )
        return [_deserialize(item, model) for item in found.get("Items", [])]
