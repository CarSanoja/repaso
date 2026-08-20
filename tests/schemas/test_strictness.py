from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from repaso.schemas import (
    EvidenceSpan,
    GradedBy,
    GradeResult,
    Item,
    ItemKind,
    Provenance,
    Source,
    Student,
)


def make_provenance() -> Provenance:
    return Provenance(source=Source.GENERATED, created_at=datetime(2026, 9, 1, tzinfo=UTC))


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        Student(
            id="s1",
            family_id="f1",
            alias="leo",
            grade=4,
            section_key="school-4-a",
            created_at=datetime(2026, 9, 1, tzinfo=UTC),
            real_name="must not exist",
        )


def test_frozen_models_are_immutable():
    student = Student(
        id="s1",
        family_id="f1",
        alias="leo",
        grade=4,
        section_key="school-4-a",
        created_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    with pytest.raises(ValidationError):
        student.alias = "other"


def test_item_difficulty_bounds():
    with pytest.raises(ValidationError):
        Item(
            id="i1",
            competency_id="c1",
            kind=ItemKind.MCQ,
            difficulty=9,
            stem="2/4 equals?",
            options=["1/2", "2/8"],
            answer_key="1/2",
            rationale="simplify",
            provenance=make_provenance(),
        )


def test_grade_result_requires_evidence():
    with pytest.raises(ValidationError):
        GradeResult(
            student_id="s1",
            item_id="i1",
            correct=True,
            confidence=0.9,
            graded_by=GradedBy.DETERMINISTIC,
            feedback="ok",
            graded_at=datetime(2026, 9, 1, tzinfo=UTC),
        )


def test_evidence_span_carries_quote():
    span = EvidenceSpan(quote="2/4 = 1/2", source_ref="response:s1:i1")
    assert span.quote
