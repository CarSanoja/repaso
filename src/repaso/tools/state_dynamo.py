from datetime import date

from repaso.config.clients import dynamodb_client
from repaso.core.harness.retention import expiry_of
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
from repaso.schemas.operation import OperationRecord
from repaso.schemas.review import QuarantineItem, QuarantineStatus
from repaso.schemas.schedule import ExamDate, SpacedItemState
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
    serialize,
)

INDEX_NAME = "gsi1"


class DynamoStateStore:
    def __init__(self, table: str) -> None:
        self._table = table

    def put_family(self, family: Family) -> None:
        put_row(self._table, f"FAMILY#{family.id}", "PROFILE", family)
        lookup = key_of(f"CHAT#{family.channel}#{family.chat_ref}", "FAMILY")
        dynamodb_client().put_item(TableName=self._table, Item=lookup | {"ref": {"S": family.id}})

    def get_family(self, family_id: FamilyId) -> Family | None:
        return get_row(self._table, f"FAMILY#{family_id}", "PROFILE", Family)

    def find_family_by_chat(self, channel: str, chat_ref: str) -> Family | None:
        found = dynamodb_client().get_item(
            TableName=self._table,
            Key=key_of(f"CHAT#{channel}#{chat_ref}", "FAMILY"),
            ConsistentRead=True,
        )
        item = found.get("Item")
        return self.get_family(FamilyId(item["ref"]["S"])) if item else None

    def list_families(self) -> list[Family]:
        return scan_profiles(self._table, "FAMILY#", Family)

    def forget_family(self, family_id: FamilyId) -> None:
        # Scan the primary table, including interrupted dual writes and legacy
        # rows. A GSI or ownership mirror alone cannot prove erasure.
        from boto3.dynamodb.types import TypeDeserializer

        family = self.get_family(family_id)
        decoder = TypeDeserializer()
        client = dynamodb_client()
        request = {"TableName": self._table, "ConsistentRead": True}
        rows = []
        while True:
            page = client.scan(**request)
            rows.extend(page.get("Items", []))
            if not page.get("LastEvaluatedKey"):
                break
            request["ExclusiveStartKey"] = page["LastEvaluatedKey"]
        decoded = [(row, decoder.deserialize(row["doc"]) if "doc" in row else {}) for row in rows]
        students = {
            doc["id"] for _, doc in decoded if doc.get("family_id") == family_id and "alias" in doc
        }
        owned = {family_id, *students}
        scopes = {family_id}
        if family:
            scopes.add(f"chat:{family.chat_ref}")
        for _, doc in decoded:
            if doc.get("family_id") == family_id or doc.get("student_id") in students:
                if doc.get("id"):
                    owned.add(doc["id"])
        deleting = []
        for row, doc in decoded:
            pk, sk = row["pk"]["S"], row["sk"]["S"]
            direct = (
                doc.get("family_id") == family_id
                or doc.get("student_id") in students
                or doc.get("scope") in scopes
            )
            partition = any(
                pk == f"{prefix}#{identity}"
                for identity in owned
                for prefix in ("FAMILY", "STUDENT", "MATERIAL", "ITEM", "SESSION", "ESC")
            )
            metadata = (
                pk.startswith("CLAIM#")
                and bool(set(pk.split("#")) & (owned | scopes))
                or pk == f"DATA#{family_id}"
                or sk == f"FAMILY#{family_id}"
            )
            chat = family and pk in {
                f"CHAT#{family.channel}#{family.chat_ref}",
                f"ENROLL#{family.channel}#{family.chat_ref}",
                f"DATA#chat:{family.chat_ref}",
            }
            if direct or partition or metadata or chat:
                deleting.append((pk, sk))

        # Retain the ownership roots until dependent deletion has completed.
        def last(key):
            pk, sk = key
            if pk == f"FAMILY#{family_id}" and sk == "PROFILE":
                return 3
            if pk == f"FAMILY#{family_id}" and sk.startswith("STUDENT#"):
                return 2
            if pk.startswith("STUDENT#") and sk == "PROFILE":
                return 1
            return 0

        for pk, sk in sorted(deleting, key=last):
            delete_row(self._table, pk, sk)

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

    def put_exam_date(self, exam: ExamDate) -> None:
        put_row(self._table, f"STUDENT#{exam.student_id}", f"EXAM#{exam.exam_date}", exam)

    def list_exam_dates(self, student_id: StudentId) -> list[ExamDate]:
        return query_prefix(self._table, f"STUDENT#{student_id}", "EXAM#", ExamDate)

    def delete_exam_date(self, student_id: StudentId, exam_date: date) -> None:
        delete_row(self._table, f"STUDENT#{student_id}", f"EXAM#{exam_date}")

    def list_family_items(self, family_id: str) -> list[Item]:
        return query_prefix(self._table, f"FAMILY#{family_id}", "ITEM#", Item)

    def put_item(self, item: Item) -> None:
        if item.family_id:
            put_row(self._table, f"FAMILY#{item.family_id}", f"ITEM#{item.id}", item)
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
        return [e for e in self.list_escalations(family_id) if e.status is EscalationStatus.PENDING]

    def put_quarantine(self, item: QuarantineItem) -> None:
        put_row(self._table, f"FAMILY#{item.family_id}", f"QUAR#{item.id}", item)

    def get_quarantine(self, family_id: FamilyId, quarantine_id: str) -> QuarantineItem | None:
        return get_row(self._table, f"FAMILY#{family_id}", f"QUAR#{quarantine_id}", QuarantineItem)

    def list_pending_quarantine(self, family_id: FamilyId) -> list[QuarantineItem]:
        found = query_prefix(self._table, f"FAMILY#{family_id}", "QUAR#", QuarantineItem)
        return [item for item in found if item.status is QuarantineStatus.PENDING]

    def put_enrollment(self, progress: EnrollmentProgress) -> None:
        put_row(self._table, f"ENROLL#{progress.channel}#{progress.chat_ref}", "PROFILE", progress)

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

    def release_claim(self, key: str, owner: str) -> None:
        from botocore.exceptions import ClientError

        try:
            dynamodb_client().delete_item(
                TableName=self._table,
                Key=key_of(f"CLAIM#{key}", "CLAIM"),
                ConditionExpression="#owner = :owner",
                ExpressionAttributeNames={"#owner": "owner"},
                ExpressionAttributeValues={":owner": {"S": owner}},
            )
        except ClientError as error:
            if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise

    def put_record(self, record: OperationRecord) -> None:
        item = key_of(f"DATA#{record.scope}", record.key) | serialize(record)
        stamp = expiry_of(record.payload)
        if stamp is not None:
            item["expires_at"] = {"N": str(int(stamp))}
        dynamodb_client().put_item(TableName=self._table, Item=item)

    def get_record(self, scope: str, key: str) -> OperationRecord | None:
        return get_row(self._table, f"DATA#{scope}", key, OperationRecord)

    def list_records(self, scope: str, prefix: str = "") -> list[OperationRecord]:
        return query_prefix(self._table, f"DATA#{scope}", prefix, OperationRecord)

    def delete_records(self, scope: str) -> None:
        for row in query_keys(self._table, f"DATA#{scope}"):
            delete_row(self._table, row["pk"]["S"], row["sk"]["S"])

    def acquire_lease(self, scope, owner, expires) -> bool:
        import time

        from botocore.exceptions import ClientError

        try:
            dynamodb_client().put_item(
                TableName=self._table,
                Item=key_of(f"LEASE#{scope}", "LEASE")
                | {
                    "owner": {"S": owner},
                    "expires": {"N": str(expires)},
                },
                ConditionExpression="attribute_not_exists(pk) OR expires < :now",
                ExpressionAttributeValues={":now": {"N": str(time.time())}},
            )
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise
        return True

    def reserve_budget(self, scope, day, limit, global_limit) -> bool:
        from botocore.exceptions import ClientError

        updates = []
        for key, cap in ((f"FAMILY#{scope}", limit), ("GLOBAL", global_limit)):
            updates.append(
                {
                    "Update": {
                        "TableName": self._table,
                        "Key": key_of(f"BUDGET#{day}", key),
                        "UpdateExpression": "ADD #used :one",
                        "ConditionExpression": "attribute_not_exists(#used) OR #used < :limit",
                        "ExpressionAttributeNames": {"#used": "used"},
                        "ExpressionAttributeValues": {
                            ":one": {"N": "1"},
                            ":limit": {"N": str(cap)},
                        },
                    }
                }
            )
        try:
            dynamodb_client().transact_write_items(TransactItems=updates)
        except ClientError as error:
            if error.response["Error"]["Code"] == "TransactionCanceledException":
                return False
            raise
        return True

    def release_lease(self, scope, owner) -> None:
        from botocore.exceptions import ClientError

        try:
            dynamodb_client().delete_item(
                TableName=self._table,
                Key=key_of(f"LEASE#{scope}", "LEASE"),
                ConditionExpression="#owner = :owner",
                ExpressionAttributeNames={"#owner": "owner"},
                ExpressionAttributeValues={":owner": {"S": owner}},
            )
        except ClientError as error:
            if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise

    def list_materials(self, family_id: str) -> list[Material]:
        return query_prefix(self._table, f"FAMILY#{family_id}", "MATERIAL#", Material)

    def list_sessions(self, student_id: str) -> list[PracticeSession]:
        return query_prefix(self._table, f"STUDENT#{student_id}", "SESSION#", PracticeSession)

    def list_quarantine(self, family_id: str) -> list[QuarantineItem]:
        return query_prefix(self._table, f"FAMILY#{family_id}", "QUAR#", QuarantineItem)

    def apply_outcome(self, key, mastery, spaced, previous) -> bool:
        from botocore.exceptions import ClientError

        client = dynamodb_client()
        marker = key_of(f"STUDENT#{mastery.student_id}", f"OUTCOME#{key}")
        if client.get_item(TableName=self._table, Key=marker, ConsistentRead=True).get("Item"):
            return True
        condition = {"ConditionExpression": "attribute_not_exists(pk)"}
        if previous is not None:
            condition = {
                "ConditionExpression": "#doc = :previous",
                "ExpressionAttributeNames": {"#doc": "doc"},
                "ExpressionAttributeValues": {":previous": serialize(previous)["doc"]},
            }
        try:
            client.transact_write_items(
                TransactItems=[
                    {
                        "Put": {
                            "TableName": self._table,
                            "Item": marker,
                            "ConditionExpression": "attribute_not_exists(pk)",
                        }
                    },
                    {
                        "Put": {
                            "TableName": self._table,
                            "Item": key_of(
                                f"STUDENT#{mastery.student_id}", f"MASTERY#{mastery.competency_id}"
                            )
                            | serialize(mastery),
                            **condition,
                        }
                    },
                    {
                        "Put": {
                            "TableName": self._table,
                            "Item": key_of(
                                f"STUDENT#{spaced.student_id}", f"SPACED#{spaced.item_id}"
                            )
                            | serialize(spaced),
                        }
                    },
                ]
            )
        except ClientError as error:
            if error.response["Error"]["Code"] == "TransactionCanceledException":
                return False
            raise
        return True
