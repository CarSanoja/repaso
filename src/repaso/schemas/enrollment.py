from enum import StrEnum

from pydantic import Field

from repaso.schemas.channel import ChannelKind
from repaso.schemas.common import Lang, StrictBaseModel


class EnrollmentStep(StrEnum):
    CONSENT = "consent"
    ALIAS = "alias"
    GRADE = "grade"
    SECTION = "section"
    SCHEDULE = "schedule"
    DONE = "done"


class EnrollmentProgress(StrictBaseModel):
    channel: ChannelKind
    chat_ref: str
    lang: Lang = Lang.ES
    step: EnrollmentStep = EnrollmentStep.CONSENT
    invite_code: str = ""
    alias: str | None = None
    grade: int | None = Field(default=None, ge=1, le=12)
    section_key: str | None = None
    practice_hour: int | None = Field(default=None, ge=0, le=23)
    practice_minute: int = Field(default=0, ge=0, le=59)
