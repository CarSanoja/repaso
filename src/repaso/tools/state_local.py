from datetime import date
from pathlib import Path

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
from repaso.tools.state_local_io import JsonTables


class LocalStateStore:
    def __init__(self, root: Path) -> None:
        self._tables = JsonTables(root)

    def put_family(self, family: Family) -> None:
        self._tables.put("families", family.id, family)

    def get_family(self, family_id: FamilyId) -> Family | None:
        return self._tables.get("families", family_id, Family)

    def find_family_by_chat(self, channel: str, chat_ref: str) -> Family | None:
        found = self._tables.where("families", Family, channel=channel, chat_ref=chat_ref)
        return found[0] if found else None

    def list_families(self) -> list[Family]:
        return self._tables.all("families", Family)

    def forget_family(self, family_id: FamilyId) -> None:
        family = self.get_family(family_id)
        students = {s.id for s in self.list_students(family_id)}
        identifiers = {family_id, *students, *(m.id for m in self.list_materials(family_id))}
        if family:
            identifiers.update({f"chat:{family.chat_ref}", f"{family.channel}#{family.chat_ref}"})
        with self._tables.exclusive():
            self._tables.recover()
            updates = {}
            for table in (
                "families",
                "students",
                "mastery",
                "spaced",
                "exams",
                "sessions",
                "materials",
                "escalations",
                "quarantine",
                "items",
                "operations",
                "outcomes",
                "enrollment",
                "claims",
                "budgets",
            ):
                kept = {}
                for key, value in self._tables.read(table).items():
                    keyed = key in identifiers or bool(set(key.split("#")) & identifiers)
                    owned = isinstance(value, dict) and (
                        value.get("family_id") == family_id
                        or value.get("student_id") in students
                        or value.get("scope") in identifiers
                    )
                    if not keyed and not owned:
                        kept[key] = value
                updates[table] = kept
            self._tables.transaction(updates)

    def put_student(self, student: Student) -> None:
        self._tables.put("students", student.id, student)

    def get_student(self, student_id: StudentId) -> Student | None:
        return self._tables.get("students", student_id, Student)

    def list_students(self, family_id: FamilyId) -> list[Student]:
        return self._tables.where("students", Student, family_id=family_id)

    def put_mastery(self, state: MasteryState) -> None:
        self._tables.put("mastery", f"{state.student_id}#{state.competency_id}", state)

    def get_mastery(
        self, student_id: StudentId, competency_id: CompetencyId
    ) -> MasteryState | None:
        return self._tables.get("mastery", f"{student_id}#{competency_id}", MasteryState)

    def list_mastery(self, student_id: StudentId) -> list[MasteryState]:
        return self._tables.where("mastery", MasteryState, student_id=student_id)

    def put_spaced(self, state: SpacedItemState) -> None:
        self._tables.put("spaced", f"{state.student_id}#{state.item_id}", state)

    def list_spaced(self, student_id: StudentId) -> list[SpacedItemState]:
        return self._tables.where("spaced", SpacedItemState, student_id=student_id)

    def put_exam_date(self, exam: ExamDate) -> None:
        self._tables.put("exams", f"{exam.student_id}#{exam.exam_date}", exam)

    def list_exam_dates(self, student_id: StudentId) -> list[ExamDate]:
        return self._tables.where("exams", ExamDate, student_id=student_id)

    def delete_exam_date(self, student_id: StudentId, exam_date: date) -> None:
        self._tables.delete("exams", f"{student_id}#{exam_date}")

    def list_family_items(self, family_id: str) -> list[Item]:
        return self._tables.where("items", Item, family_id=family_id)

    def put_item(self, item: Item) -> None:
        self._tables.put("items", item.id, item)

    def get_item(self, item_id: ItemId) -> Item | None:
        return self._tables.get("items", item_id, Item)

    def list_items_by_competency(
        self, competency_id: CompetencyId, status: ItemStatus | None = None
    ) -> list[Item]:
        found = self._tables.where("items", Item, competency_id=competency_id)
        return found if status is None else [item for item in found if item.status is status]

    def put_material(self, material: Material) -> None:
        self._tables.put("materials", material.id, material)

    def get_material(self, material_id: MaterialId) -> Material | None:
        return self._tables.get("materials", material_id, Material)

    def put_session(self, session: PracticeSession) -> None:
        self._tables.put("sessions", session.id, session)

    def get_session(self, session_id: SessionId) -> PracticeSession | None:
        return self._tables.get("sessions", session_id, PracticeSession)

    def get_session_by_date(
        self, student_id: StudentId, session_date: date
    ) -> PracticeSession | None:
        found = self._tables.where(
            "sessions", PracticeSession, student_id=student_id, session_date=session_date
        )
        return found[0] if found else None

    def put_escalation(self, escalation: Escalation) -> None:
        self._tables.put("escalations", escalation.id, escalation)

    def get_escalation(self, escalation_id: EscalationId) -> Escalation | None:
        return self._tables.get("escalations", escalation_id, Escalation)

    def list_escalations(self, family_id: FamilyId) -> list[Escalation]:
        return self._tables.where("escalations", Escalation, family_id=family_id)

    def list_pending_escalations(self, family_id: FamilyId) -> list[Escalation]:
        pending = EscalationStatus.PENDING
        return self._tables.where("escalations", Escalation, family_id=family_id, status=pending)

    def put_quarantine(self, item: QuarantineItem) -> None:
        self._tables.put("quarantine", item.id, item)

    def get_quarantine(self, family_id: FamilyId, quarantine_id: str) -> QuarantineItem | None:
        item = self._tables.get("quarantine", quarantine_id, QuarantineItem)
        return item if item is not None and item.family_id == family_id else None

    def list_pending_quarantine(self, family_id: FamilyId) -> list[QuarantineItem]:
        pending = QuarantineStatus.PENDING
        return self._tables.where("quarantine", QuarantineItem, family_id=family_id, status=pending)

    def put_enrollment(self, progress: EnrollmentProgress) -> None:
        self._tables.put("enrollment", f"{progress.channel}#{progress.chat_ref}", progress)

    def get_enrollment(self, channel: str, chat_ref: str) -> EnrollmentProgress | None:
        return self._tables.get("enrollment", f"{channel}#{chat_ref}", EnrollmentProgress)

    def delete_enrollment(self, channel: str, chat_ref: str) -> None:
        self._tables.delete("enrollment", f"{channel}#{chat_ref}")

    def claim(self, key: str, owner: str) -> bool:
        return self._tables.claim("claims", key, owner)

    def release_claim(self, key: str, owner: str) -> None:
        with self._tables.exclusive():
            rows = self._tables.read("claims")
            if rows.get(key) == owner:
                rows.pop(key)
                self._tables.write("claims", rows)

    def put_record(self, record: OperationRecord) -> None:
        self._tables.put("operations", f"{record.scope}#{record.key}", record)

    def get_record(self, scope: str, key: str) -> OperationRecord | None:
        return self._tables.get("operations", f"{scope}#{key}", OperationRecord)

    def list_records(self, scope: str, prefix: str = "") -> list[OperationRecord]:
        return [
            r
            for r in self._tables.where("operations", OperationRecord, scope=scope)
            if r.key.startswith(prefix)
        ]

    def delete_records(self, scope: str) -> None:
        self._tables.delete_where("operations", OperationRecord, scope=scope)

    def acquire_lease(self, scope, owner, expires) -> bool:
        import time

        with self._tables.exclusive():
            rows = self._tables.read("leases")
            previous = rows.get(scope)
            if previous and previous["expires"] > time.time():
                return False
            rows[scope] = {"owner": owner, "expires": expires}
            self._tables.write("leases", rows)
            return True

    def reserve_budget(self, scope, day, limit, global_limit) -> bool:
        with self._tables.exclusive():
            rows = self._tables.read("budgets")
            family_key, global_key = f"{day}#{scope}", f"{day}#GLOBAL"
            if rows.get(family_key, 0) >= limit or rows.get(global_key, 0) >= global_limit:
                return False
            rows[family_key] = rows.get(family_key, 0) + 1
            rows[global_key] = rows.get(global_key, 0) + 1
            self._tables.write("budgets", rows)
            return True

    def release_lease(self, scope, owner) -> None:
        with self._tables.exclusive():
            rows = self._tables.read("leases")
            if rows.get(scope, {}).get("owner") == owner:
                rows.pop(scope)
                self._tables.write("leases", rows)

    def list_materials(self, family_id: str) -> list[Material]:
        return self._tables.where("materials", Material, family_id=family_id)

    def list_sessions(self, student_id: str) -> list[PracticeSession]:
        return self._tables.where("sessions", PracticeSession, student_id=student_id)

    def list_quarantine(self, family_id: str) -> list[QuarantineItem]:
        return self._tables.where("quarantine", QuarantineItem, family_id=family_id)

    def apply_outcome(self, key, mastery, spaced, previous) -> bool:
        with self._tables.exclusive():
            self._tables.recover()
            markers = self._tables.read("outcomes")
            marker = f"{mastery.student_id}#{key}"
            if marker in markers:
                return True
            states = self._tables.read("mastery")
            state_key = f"{mastery.student_id}#{mastery.competency_id}"
            expected = previous.model_dump(mode="json") if previous else None
            if states.get(state_key) != expected:
                return False
            spacing = self._tables.read("spaced")
            states[state_key] = mastery.model_dump(mode="json")
            spacing[f"{spaced.student_id}#{spaced.item_id}"] = spaced.model_dump(mode="json")
            markers[marker] = {"student_id": mastery.student_id}
            self._tables.transaction({"mastery": states, "spaced": spacing, "outcomes": markers})
            return True
