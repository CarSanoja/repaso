from datetime import datetime
from uuid import uuid4

from pydantic import Field

from repaso.agents.base import StructuredCallFailed, structured
from repaso.agents.prompts.grader import PROMPT_VERSION, SYSTEM
from repaso.schemas.common import FamilyId, Lang, StrictBaseModel
from repaso.schemas.grading import EvidenceSpan, GradedBy, GradeResult, StudentResponse
from repaso.schemas.item import Item
from repaso.schemas.review import HeldAnswer, QuarantineItem, QuarantineKind

NO_RUBRIC = "No rubric was written for this item; grade strictly against the answer key."


class OpenGrade(StrictBaseModel):
    correct: bool
    rubric_points: float = Field(ge=0.0, le=2.0)
    confidence: float = Field(ge=0.0, le=1.0)
    feedback: str


def normalize(text: str) -> str:
    return text.strip().casefold()


def evidence_for(response: StudentResponse) -> EvidenceSpan:
    return EvidenceSpan(
        quote=response.text,
        source_ref=f"response:{response.student_id}:{response.item_id}",
    )


def mcq_matches(item: Item, reply: str) -> bool:
    key = normalize(item.answer_key)
    if reply == key:
        return True
    options = [normalize(option) for option in item.options]
    if key not in options:
        return False
    return reply == str(options.index(key) + 1)


def grade_mcq(item: Item, response: StudentResponse, graded_at: datetime) -> GradeResult:
    return GradeResult(
        student_id=response.student_id,
        item_id=response.item_id,
        correct=mcq_matches(item, normalize(response.text)),
        rubric_points=None,
        confidence=1.0,
        graded_by=GradedBy.DETERMINISTIC,
        latency_seconds=response.latency_seconds,
        evidence=evidence_for(response),
        feedback="",
        quarantined=False,
        graded_at=graded_at,
    )


def open_prompt(item: Item, answer: str, lang: Lang) -> str:
    return (
        f"Question: {item.stem}\n"
        f"Answer key: {item.answer_key}\n"
        f"Rubric: {item.rubric or NO_RUBRIC}\n"
        f"Student answer, verbatim: {answer}\n"
        f"Write the feedback field in {lang.value}, addressed to the child."
    )


def quarantine_for(
    response: StudentResponse,
    family_id: FamilyId,
    graded_at: datetime,
) -> QuarantineItem:
    return QuarantineItem(
        id=uuid4().hex,
        kind=QuarantineKind.LOW_CONFIDENCE_GRADE,
        family_id=family_id,
        evidence=evidence_for(response),
        payload=HeldAnswer(
            item_id=response.item_id,
            student_id=response.student_id,
            answer=response.text,
            latency_seconds=response.latency_seconds,
        ).model_dump(),
        created_at=graded_at,
    )


def held_back(
    response: StudentResponse,
    family_id: FamilyId,
    confidence: float,
    graded_at: datetime,
) -> tuple[GradeResult, QuarantineItem]:
    result = GradeResult(
        student_id=response.student_id,
        item_id=response.item_id,
        correct=None,
        rubric_points=None,
        confidence=confidence,
        graded_by=GradedBy.LLM,
        latency_seconds=response.latency_seconds,
        evidence=evidence_for(response),
        feedback="",
        quarantined=True,
        graded_at=graded_at,
    )
    return result, quarantine_for(response, family_id, graded_at)


async def grade_open(
    item: Item,
    response: StudentResponse,
    lang: Lang,
    model,
    confidence_threshold: float,
    graded_at: datetime,
    family_id: FamilyId,
    *,
    llm_text: str | None = None,
) -> tuple[GradeResult, QuarantineItem | None]:
    try:
        reply = await structured(
            model,
            OpenGrade,
            SYSTEM.format(lang=lang.value),
            open_prompt(item, response.text if llm_text is None else llm_text, lang),
            PROMPT_VERSION,
        )
    except StructuredCallFailed:
        return held_back(response, family_id, 0.0, graded_at)
    if reply.confidence < confidence_threshold:
        return held_back(response, family_id, reply.confidence, graded_at)
    result = GradeResult(
        student_id=response.student_id,
        item_id=response.item_id,
        correct=reply.correct,
        rubric_points=reply.rubric_points,
        confidence=reply.confidence,
        graded_by=GradedBy.LLM,
        latency_seconds=response.latency_seconds,
        evidence=evidence_for(response),
        feedback=reply.feedback,
        quarantined=False,
        graded_at=graded_at,
    )
    return result, None
