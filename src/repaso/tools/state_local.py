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
        for student in self.list_students(family_id):
            self._tables.delete_where("mastery", MasteryState, student_id=student.id)
            self._tables.delete_where("spaced", SpacedItemState, student_id=student.id)
            self._tables.delete_where("exams", ExamDate, student_id=student.id)
            self._tables.delete_where("sessions", PracticeSession, student_id=student.id)
        self._tables.delete_where("students", Student, family_id=family_id)
        self._tables.delete_where("materials", Material, family_id=family_id)
        self._tables.delete_where("escalations", Escalation, family_id=family_id)
        self._tables.delete_where("quarantine", QuarantineItem, family_id=family_id)
        if family is not None:
            self._tables.delete("enrollment", f"{family.channel}#{family.chat_ref}")
        self._tables.delete("families", family_id)

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
