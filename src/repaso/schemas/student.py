from datetime import datetime

from pydantic import Field

from repaso.schemas.common import FamilyId, FrozenStrictModel, StudentId


class Student(FrozenStrictModel):
    id: StudentId
    family_id: FamilyId
    alias: str = Field(min_length=1, max_length=40)
    grade: int = Field(ge=1, le=12)
    section_key: str
    created_at: datetime
