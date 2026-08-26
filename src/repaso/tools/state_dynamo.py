from datetime import date

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
from repaso.schemas.enrollment import EnrollmentProgress
from repaso.schemas.escalation import Escalation, EscalationStatus
from repaso.schemas.family import Family
from repaso.schemas.item import Item, ItemStatus
from repaso.schemas.mastery import MasteryState
from repaso.schemas.material import Material
from repaso.schemas.review import QuarantineItem, QuarantineStatus
from repaso.schemas.schedule import SpacedItemState
from repaso.schemas.session import PracticeSession
from repaso.schemas.student import Student
from repaso.tools.state_dynamo_io import (
    delete_row,
    get_row,
    key_of,
    put_row,
    query_index,
    query_keys,
    query_prefix,
    scan_profiles,
)

INDEX_NAME = "gsi1"


class DynamoStateStore:
    def __init__(self, table: str) -> None:
        self._table = table

    def put_family(self, family: Family) -> None:
        put_row(self._table, f"FAMILY#{family.id}", "PROFILE", family)
        lookup = key_of(f"CHAT#{family.channel}#{family.chat_ref}", "FAMILY")
        dynamodb_client().put_item(
            TableName=self._table, Item=lookup | {"ref": {"S": family.id}}
        )

    def get_family(self, family_id: FamilyId) -> Family | None:
        return get_row(self._table, f"FAMILY#{family_id}", "PROFILE", Family)

    def find_family_by_chat(self, channel: str, chat_ref: str) -> Family | None:
        found = dynamodb_client().get_item(
            TableName=self._table, Key=key_of(f"CHAT#{channel}#{chat_ref}", "FAMILY")
        )
        item = found.get("Item")
        return self.get_family(FamilyId(item["ref"]["S"])) if item else None

    def list_families(self) -> list[Family]:
        return scan_profiles(self._table, "FAMILY#", Family)

    def forget_family(self, family_id: FamilyId) -> None:
        family = self.get_family(family_id)
        for student in self.list_students(family_id):
            for row in query_keys(self._table, f"STUDENT#{student.id}"):
                delete_row(self._table, row["pk"]["S"], row["sk"]["S"])
        for row in query_keys(self._table, f"FAMILY#{family_id}"):
            delete_row(self._table, row["pk"]["S"], row["sk"]["S"])
        if family is not None:
            delete_row(self._table, f"CHAT#{family.channel}#{family.chat_ref}", "FAMILY")
            delete_row(self._table, f"ENROLL#{family.channel}#{family.chat_ref}", "PROFILE")

    def put_student(self, student: Student) -> None:
        put_row(self._table, f"FAMILY#{student.family_id}", f"STUDENT#{student.id}", student)
        put_row(self._table, f"STUDENT#{student.id}", "PROFILE", student)

    def get_student(self, student_id: StudentId) -> Student | None:
        return get_row(self._table, f"STUDENT#{student_id}", "PROFILE", Student)

    def list_students(self, family_id: FamilyId) -> list[Student]:
        return query_prefix(self._table, f"FAMILY#{family_id}", "STUDENT#", Student)

    def put_mastery(self, state: MasteryState) -> None:
        put_row(self._table, f"STUDENT#{state.student_id}", f"MASTERY#{state.competency_id}", state)

    def get_mastery(
        self, student_id: StudentId, competency_id: CompetencyId
    ) -> MasteryState | None:
        sk = f"MASTERY#{competency_id}"
        return get_row(self._table, f"STUDENT#{student_id}", sk, MasteryState)

    def list_mastery(self, student_id: StudentId) -> list[MasteryState]:
        return query_prefix(self._table, f"STUDENT#{student_id}", "MASTERY#", MasteryState)

    def put_spaced(self, state: SpacedItemState) -> None:
        put_row(self._table, f"STUDENT#{state.student_id}", f"SPACED#{state.item_id}", state)

    def list_spaced(self, student_id: StudentId) -> list[SpacedItemState]:
        return query_prefix(self._table, f"STUDENT#{student_id}", "SPACED#", SpacedItemState)

    def put_item(self, item: Item) -> None:
        gsi1 = (f"COMP#{item.competency_id}", f"ITEM#{item.id}")
        put_row(self._table, f"ITEM#{item.id}", "PROFILE", item, gsi1)

    def get_item(self, item_id: ItemId) -> Item | None:
        return get_row(self._table, f"ITEM#{item_id}", "PROFILE", Item)

    def list_items_by_competency(
        self, competency_id: CompetencyId, status: ItemStatus | None = None
    ) -> list[Item]:
        found = query_index(self._table, INDEX_NAME, f"COMP#{competency_id}", Item)
        return found if status is None else [item for item in found if item.status is status]

    def put_material(self, material: Material) -> None:
        put_row(self._table, f"MATERIAL#{material.id}", "PROFILE", material)
        put_row(self._table, f"FAMILY#{material.family_id}", f"MATERIAL#{material.id}", material)

    def get_material(self, material_id: MaterialId) -> Material | None:
        return get_row(self._table, f"MATERIAL#{material_id}", "PROFILE", Material)

    def put_session(self, session: PracticeSession) -> None:
        sk = f"SESSION#{session.session_date}"
        put_row(self._table, f"STUDENT#{session.student_id}", sk, session)
        put_row(self._table, f"SESSION#{session.id}", "PROFILE", session)

    def get_session(self, session_id: SessionId) -> PracticeSession | None:
        return get_row(self._table, f"SESSION#{session_id}", "PROFILE", PracticeSession)

    def get_session_by_date(
        self, student_id: StudentId, session_date: date
    ) -> PracticeSession | None:
        return get_row(
            self._table, f"STUDENT#{student_id}", f"SESSION#{session_date}", PracticeSession
        )

    def put_escalation(self, escalation: Escalation) -> None:
        pending = escalation.status is EscalationStatus.PENDING
        gsi1 = (f"ESCPENDING#{escalation.family_id}", f"ESC#{escalation.id}") if pending else None
        pk = f"FAMILY#{escalation.family_id}"
        put_row(self._table, pk, f"ESC#{escalation.id}", escalation, gsi1)
        put_row(self._table, f"ESC#{escalation.id}", "PROFILE", escalation)

    def get_escalation(self, escalation_id: EscalationId) -> Escalation | None:
        return get_row(self._table, f"ESC#{escalation_id}", "PROFILE", Escalation)

    def list_escalations(self, family_id: FamilyId) -> list[Escalation]:
        return query_prefix(self._table, f"FAMILY#{family_id}", "ESC#", Escalation)

    def list_pending_escalations(self, family_id: FamilyId) -> list[Escalation]:
        return query_index(self._table, INDEX_NAME, f"ESCPENDING#{family_id}", Escalation)

    def put_quarantine(self, item: QuarantineItem) -> None:
        put_row(self._table, f"FAMILY#{item.family_id}", f"QUAR#{item.id}", item)

    def list_pending_quarantine(self, family_id: FamilyId) -> list[QuarantineItem]:
        found = query_prefix(self._table, f"FAMILY#{family_id}", "QUAR#", QuarantineItem)
        return [item for item in found if item.status is QuarantineStatus.PENDING]

    def put_enrollment(self, progress: EnrollmentProgress) -> None:
        put_row(
            self._table, f"ENROLL#{progress.channel}#{progress.chat_ref}", "PROFILE", progress
        )

    def get_enrollment(self, channel: str, chat_ref: str) -> EnrollmentProgress | None:
        return get_row(self._table, f"ENROLL#{channel}#{chat_ref}", "PROFILE", EnrollmentProgress)

    def delete_enrollment(self, channel: str, chat_ref: str) -> None:
        delete_row(self._table, f"ENROLL#{channel}#{chat_ref}", "PROFILE")

    def claim(self, key: str, owner: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            dynamodb_client().put_item(
                TableName=self._table,
                Item=key_of(f"CLAIM#{key}", "CLAIM") | {"owner": {"S": owner}},
                ConditionExpression="attribute_not_exists(pk)",
            )
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise
        return True
