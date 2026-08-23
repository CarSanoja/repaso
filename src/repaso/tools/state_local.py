import json
import os
import threading
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import BaseModel

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


class LocalStateStore:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._lock = threading.Lock()
        self._root.mkdir(parents=True, exist_ok=True)

    def put_family(self, family: Family) -> None:
        self._put("families", family.id, family)

    def get_family(self, family_id: FamilyId) -> Family | None:
        return self._get("families", family_id, Family)

    def find_family_by_chat(self, channel: str, chat_ref: str) -> Family | None:
        found = self._where("families", Family, channel=channel, chat_ref=chat_ref)
        return found[0] if found else None

    def list_families(self) -> list[Family]:
        return self._all("families", Family)

    def forget_family(self, family_id: FamilyId) -> None:
        family = self.get_family(family_id)
        for student in self.list_students(family_id):
            self._delete_where("mastery", MasteryState, student_id=student.id)
            self._delete_where("spaced", SpacedItemState, student_id=student.id)
            self._delete_where("sessions", PracticeSession, student_id=student.id)
        self._delete_where("students", Student, family_id=family_id)
        self._delete_where("materials", Material, family_id=family_id)
        self._delete_where("escalations", Escalation, family_id=family_id)
        self._delete_where("quarantine", QuarantineItem, family_id=family_id)
        if family is not None:
            self._delete("enrollment", f"{family.channel}#{family.chat_ref}")
        self._delete("families", family_id)

    def put_student(self, student: Student) -> None:
        self._put("students", student.id, student)

    def get_student(self, student_id: StudentId) -> Student | None:
        return self._get("students", student_id, Student)

    def list_students(self, family_id: FamilyId) -> list[Student]:
        return self._where("students", Student, family_id=family_id)

    def put_mastery(self, state: MasteryState) -> None:
        self._put("mastery", f"{state.student_id}#{state.competency_id}", state)

    def get_mastery(
        self, student_id: StudentId, competency_id: CompetencyId
    ) -> MasteryState | None:
        return self._get("mastery", f"{student_id}#{competency_id}", MasteryState)

    def list_mastery(self, student_id: StudentId) -> list[MasteryState]:
        return self._where("mastery", MasteryState, student_id=student_id)

    def put_spaced(self, state: SpacedItemState) -> None:
        self._put("spaced", f"{state.student_id}#{state.item_id}", state)

    def list_spaced(self, student_id: StudentId) -> list[SpacedItemState]:
        return self._where("spaced", SpacedItemState, student_id=student_id)

    def put_item(self, item: Item) -> None:
        self._put("items", item.id, item)

    def get_item(self, item_id: ItemId) -> Item | None:
        return self._get("items", item_id, Item)

    def list_items_by_competency(
        self, competency_id: CompetencyId, status: ItemStatus | None = None
    ) -> list[Item]:
        found = self._where("items", Item, competency_id=competency_id)
        return found if status is None else [item for item in found if item.status is status]

    def put_material(self, material: Material) -> None:
        self._put("materials", material.id, material)

    def get_material(self, material_id: MaterialId) -> Material | None:
        return self._get("materials", material_id, Material)

    def put_session(self, session: PracticeSession) -> None:
        self._put("sessions", session.id, session)

    def get_session(self, session_id: SessionId) -> PracticeSession | None:
        return self._get("sessions", session_id, PracticeSession)

    def get_session_by_date(
        self, student_id: StudentId, session_date: date
    ) -> PracticeSession | None:
        found = self._where(
            "sessions", PracticeSession, student_id=student_id, session_date=session_date
        )
        return found[0] if found else None

    def put_escalation(self, escalation: Escalation) -> None:
        self._put("escalations", escalation.id, escalation)

    def get_escalation(self, escalation_id: EscalationId) -> Escalation | None:
        return self._get("escalations", escalation_id, Escalation)

    def list_pending_escalations(self, family_id: FamilyId) -> list[Escalation]:
        pending = EscalationStatus.PENDING
        return self._where("escalations", Escalation, family_id=family_id, status=pending)

    def put_quarantine(self, item: QuarantineItem) -> None:
        self._put("quarantine", item.id, item)

    def list_pending_quarantine(self, family_id: FamilyId) -> list[QuarantineItem]:
        pending = QuarantineStatus.PENDING
        return self._where("quarantine", QuarantineItem, family_id=family_id, status=pending)

    def put_enrollment(self, progress: EnrollmentProgress) -> None:
        self._put("enrollment", f"{progress.channel}#{progress.chat_ref}", progress)

    def get_enrollment(self, channel: str, chat_ref: str) -> EnrollmentProgress | None:
        return self._get("enrollment", f"{channel}#{chat_ref}", EnrollmentProgress)

    def delete_enrollment(self, channel: str, chat_ref: str) -> None:
        self._delete("enrollment", f"{channel}#{chat_ref}")

    def claim(self, key: str, owner: str) -> bool:
        with self._lock:
            claims = self._read("claims")
            if key in claims:
                return False
            claims[key] = owner
            self._write("claims", claims)
            return True

    def _read(self, table: str) -> dict[str, Any]:
        path = self._root / f"{table}.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _write(self, table: str, rows: dict[str, Any]) -> None:
        path = self._root / f"{table}.json"
        temp = path.with_name(f"{table}.{os.getpid()}.tmp")
        temp.write_text(json.dumps(rows, sort_keys=True), encoding="utf-8")
        os.replace(temp, path)

    def _put(self, table: str, key: str, model: BaseModel) -> None:
        with self._lock:
            rows = self._read(table)
            rows[key] = model.model_dump(mode="json")
            self._write(table, rows)

    def _delete(self, table: str, key: str) -> None:
        with self._lock:
            rows = self._read(table)
            if key in rows:
                del rows[key]
                self._write(table, rows)

    def _get[M: BaseModel](self, table: str, key: str, model: type[M]) -> M | None:
        row = self._read(table).get(key)
        return model.model_validate(row) if row is not None else None

    def _all[M: BaseModel](self, table: str, model: type[M]) -> list[M]:
        return [model.model_validate(row) for row in self._read(table).values()]

    def _where[M: BaseModel](self, table: str, model: type[M], **fields: Any) -> list[M]:
        rows = self._all(table, model)
        return [row for row in rows if all(getattr(row, k) == v for k, v in fields.items())]

    def _delete_where[M: BaseModel](self, table: str, model: type[M], **fields: Any) -> None:
        with self._lock:
            rows = self._read(table)
            kept = {
                key: row
                for key, row in rows.items()
                if not all(
                    getattr(model.model_validate(row), k) == v for k, v in fields.items()
                )
            }
            if len(kept) != len(rows):
                self._write(table, kept)
