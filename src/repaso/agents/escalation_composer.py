from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel

from repaso.agents.base import StructuredCallFailed, structured
from repaso.agents.prompts.escalation_composer import (
    COHORT_REQUEST,
    STRUGGLE_REQUEST,
    SYSTEM,
)
from repaso.config.models import ModelRole
from repaso.i18n.catalog import msg
from repaso.i18n.competencies import competency_label
from repaso.schemas.common import EscalationId, FamilyId, Lang, StudentId
from repaso.schemas.competency import Competency
from repaso.schemas.escalation import Escalation, EscalationKind, EscalationOption
from repaso.schemas.grading import EvidenceSpan

NOTE_ROLE = ModelRole.GENERATE
EVIDENCE_SEPARATOR = "; "
OPTION_MESSAGE_KEYS: tuple[tuple[str, str], ...] = (
    ("teacher_note", "option_teacher_note"),
    ("reduce_load", "option_reduce_load"),
)


class TeacherNote(BaseModel):
    text: str


def new_escalation_id() -> EscalationId:
    return EscalationId(uuid4().hex)


def triage_options(lang: Lang) -> list[EscalationOption]:
    return [
        EscalationOption(key=key, label=msg(message_key, lang), tradeoff="")
        for key, message_key in OPTION_MESSAGE_KEYS
    ]


def evidence_digest(evidence: list[EvidenceSpan]) -> str:
    return EVIDENCE_SEPARATOR.join(span.quote for span in evidence)


async def draft_note(model, text: str) -> str | None:
    try:
        note = await structured(model, TeacherNote, SYSTEM, text)
    except StructuredCallFailed:
        return None
    return note.text


async def compose_struggle(
    family_id: str,
    student_id: str,
    alias: str,
    competency: Competency,
    evidence: list[EvidenceSpan],
    lang: Lang,
    model,
    now: datetime,
) -> Escalation:
    summary = msg(
        "struggle_summary",
        lang,
        alias=alias,
        competency=competency_label(competency, lang),
        evidence=evidence_digest(evidence),
    )
    request = STRUGGLE_REQUEST.format(
        lang=lang.value,
        competency=competency_label(competency, lang),
        evidence_count=len(evidence),
    )
    return Escalation(
        id=new_escalation_id(),
        kind=EscalationKind.STRUGGLE_TRIAGE,
        competency_id=competency.id,
        family_id=FamilyId(family_id),
        student_id=StudentId(student_id),
        summary=summary,
        evidence=list(evidence),
        options=triage_options(lang),
        drafted_note=await draft_note(model, request),
        created_at=now,
    )


def compose_rephoto(family_id: str, lang: Lang, now: datetime) -> Escalation:
    return Escalation(
        id=new_escalation_id(),
        kind=EscalationKind.REPHOTO_REQUEST,
        family_id=FamilyId(family_id),
        summary=msg("rephoto_request", lang),
        created_at=now,
    )


def compose_engagement(
    family_id: str,
    student_id: str,
    alias: str,
    days: int,
    lang: Lang,
    now: datetime,
) -> Escalation:
    return Escalation(
        id=new_escalation_id(),
        kind=EscalationKind.ENGAGEMENT,
        family_id=FamilyId(family_id),
        student_id=StudentId(student_id),
        summary=msg("engagement_alert", lang, alias=alias, days=days),
        created_at=now,
    )


async def compose_cohort(
    section_key: str,
    competency: Competency,
    count: int,
    lang: Lang,
    model,
    now: datetime,
    family_id: str,
) -> Escalation:
    summary = msg(
        "cohort_note_intro",
        lang,
        count=count,
        section=section_key,
        competency=competency_label(competency, lang),
    )
    request = COHORT_REQUEST.format(
        lang=lang.value,
        competency=competency_label(competency, lang),
        section=section_key,
        count=count,
    )
    return Escalation(
        id=new_escalation_id(),
        kind=EscalationKind.COHORT_SIGNAL,
        competency_id=competency.id,
        family_id=FamilyId(family_id),
        summary=summary,
        drafted_note=await draft_note(model, request),
        created_at=now,
    )
