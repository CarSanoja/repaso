from datetime import UTC, date, datetime, timedelta

import pytest

from repaso.agents import escalation_composer as composer
from repaso.agents import item_optimizer as optimizer
from repaso.agents.goal_verifier import verify_daily
from repaso.core.cohort.signal import CohortFailure, evaluate, signal_claim_key
from repaso.core.harness.budgets import BoundedAttempts
from repaso.schemas.cohort import CohortKey
from repaso.schemas.common import Lang
from repaso.schemas.competency import Competency
from repaso.schemas.escalation import Escalation, EscalationKind
from repaso.schemas.grading import EvidenceSpan, GradedBy, GradeResult, StudentResponse
from repaso.schemas.item import Item, ItemKind, ItemStatus
from repaso.schemas.provenance import Provenance, Source
from repaso.schemas.review import QuarantineItem, QuarantineKind
from repaso.schemas.session import PracticeSession, SessionStatus
from repaso.tools.llm import LocalPlaybackModel

ALIAS = "Estrella"
NOW = datetime(2026, 8, 20, 19, 0, tzinfo=UTC)
TODAY = NOW.date()
SECTION = "San Jose 4to B"
FRACTIONS = Competency(id="c-fractions", subject="math", grade=4, name="Fracciones equivalentes",
                       description="Comparar y sumar fracciones con distinto denominador")
EVIDENCE = [EvidenceSpan(quote="1/2 + 1/3 = 2/5", source_ref="resp-1"),
            EvidenceSpan(quote="3/4 = 6/12", source_ref="resp-2")]
PATTERNS = {"i-all-correct": "11111111", "i-flat": "11110000", "i-healthy": "01011111",
            "f-one": "00011110", "f-two": "10101010"}


class RecordingModel(LocalPlaybackModel):
    def __init__(self, script=None) -> None:
        super().__init__(script)
        self.prompts: list[str] = []

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        self.prompts.append(str(prompt))
        async for event in super().structured_output(output_model, prompt, system_prompt, **kwargs):
            yield event


class BrokenModel:
    def structured_output(self, output_model, prompt, system_prompt=None):
        async def failing():
            raise RuntimeError("bedrock unavailable")
            yield {}

        return failing()


def make_grade(student_id: str, item_id: str, correct: bool | None) -> GradeResult:
    return GradeResult(student_id=student_id, item_id=item_id, correct=correct, confidence=0.9,
                       graded_by=GradedBy.DETERMINISTIC, evidence=EVIDENCE[0], feedback="",
                       graded_at=NOW)


def make_item(item_id: str, status: ItemStatus) -> Item:
    return Item(id=item_id, competency_id=FRACTIONS.id, kind=ItemKind.OPEN, difficulty=3,
                stem="Suma 1/2 + 1/3", answer_key="5/6", rationale="denominador comun",
                status=status, provenance=Provenance(source=Source.GENERATED, created_at=NOW))


def make_response(student_id: str, item_id: str) -> StudentResponse:
    return StudentResponse(student_id=student_id, item_id=item_id, text="respuesta",
                           latency_seconds=12.0, received_at=NOW)


def scored_grades() -> list[GradeResult]:
    return [make_grade(f"s{index}", item_id, flag == "1")
            for item_id, pattern in PATTERNS.items() for index, flag in enumerate(pattern)]


def failure(family_id: str, days_ago: int, section_key: str = "4B") -> CohortFailure:
    return CohortFailure(family_id=family_id, section_key=section_key,
                         competency_id=FRACTIONS.id, failed_on=TODAY - timedelta(days=days_ago))


async def struggle(model) -> Escalation:
    return await composer.compose_struggle("fam-1", "st-1", ALIAS, FRACTIONS, EVIDENCE,
                                           Lang.ES, model, NOW)


FAILURES = [failure("f1", 0), failure("f1", 1), failure("f2", 2), failure("f4", 3),
            failure("f3", 9), failure("f5", 0, "5A")]
COHORT = CohortKey(section_key="4B", competency_id=FRACTIONS.id)


async def test_struggle_escalation_carries_three_options_and_a_drafted_note():
    model = RecordingModel([composer.TeacherNote(text="Buenas tardes, hemos notado...")])
    escalation = await struggle(model)
    keys = [option.key for option in escalation.options]
    assert escalation.kind is EscalationKind.STRUGGLE_TRIAGE
    assert keys == ["guided_session", "teacher_note", "reduce_load"]
    assert escalation.options[1].label.startswith("Nota para la maestra")
    assert [option.tradeoff for option in escalation.options] == ["", "", ""]
    assert escalation.drafted_note == "Buenas tardes, hemos notado..."
    assert ALIAS in escalation.summary
    assert "1/2 + 1/3 = 2/5; 3/4 = 6/12" in escalation.summary


async def test_the_teacher_note_prompt_never_carries_the_alias_or_the_quotes():
    model = RecordingModel([{"text": "nota"}])
    await struggle(model)
    sent = "".join(model.prompts) + str(model.calls)
    assert ALIAS not in sent
    assert EVIDENCE[0].quote not in sent
    assert FRACTIONS.name in sent
    assert [call["kind"] for call in model.calls] == ["structured_output"]


async def test_struggle_survives_a_broken_model_without_a_note():
    escalation = await struggle(BrokenModel())
    assert escalation.drafted_note is None
    assert len(escalation.options) == 3
    assert escalation.evidence == EVIDENCE


def test_rephoto_and_engagement_need_no_model():
    rephoto = composer.compose_rephoto("fam-1", Lang.ES, NOW)
    engagement = composer.compose_engagement("fam-1", "st-1", ALIAS, 4, Lang.ES, NOW)
    assert rephoto.kind is EscalationKind.REPHOTO_REQUEST and rephoto.options == []
    assert engagement.kind is EscalationKind.ENGAGEMENT
    assert "Estrella lleva 4 días sin practicar" in engagement.summary


async def test_cohort_escalation_counts_families_and_names_nobody():
    model = RecordingModel([{"text": "Varias familias de la seccion..."}])
    escalation = await composer.compose_cohort(SECTION, FRACTIONS, 3, Lang.ES, model, NOW, "fam-1")
    assert escalation.kind is EscalationKind.COHORT_SIGNAL
    assert f"3 familias de {SECTION}" in escalation.summary
    assert escalation.drafted_note == "Varias familias de la seccion..."
    assert ALIAS not in "".join(model.prompts)


def test_cohort_fires_only_at_enough_distinct_families_inside_the_window():
    assert evaluate(FAILURES, 3, 7, TODAY) == [COHORT]
    assert evaluate(FAILURES, 4, 7, TODAY) == []
    assert evaluate(FAILURES, 4, 14, TODAY) == [COHORT]
    assert evaluate([failure("f1", 0), failure("f1", 1)], 2, 7, TODAY) == []


def test_signal_claim_key_is_stable_across_the_iso_week():
    assert signal_claim_key(COHORT, date(2026, 8, 17)) == "cohort#4B#c-fractions#2026-W34"
    assert signal_claim_key(COHORT, date(2026, 8, 20)) == "cohort#4B#c-fractions#2026-W34"
    assert signal_claim_key(COHORT, date(2026, 8, 24)) == "cohort#4B#c-fractions#2026-W35"


def test_daily_close_reports_the_planted_gap_and_spends_rework():
    sessions = [
        PracticeSession(id="ses-done", student_id="st1", session_date=TODAY,
                        status=SessionStatus.COMPLETED),
        PracticeSession(id="ses-stuck", student_id="st2", session_date=TODAY),
        PracticeSession(id="ses-later", student_id="st3", session_date=TODAY + timedelta(days=1)),
    ]
    quarantines = [QuarantineItem(id="q1", kind=QuarantineKind.LOW_CONFIDENCE_GRADE,
                                  family_id="fam-1", evidence=EVIDENCE[0], payload={},
                                  created_at=NOW)]
    escalations = [composer.compose_rephoto("fam-1", Lang.ES, NOW),
                   composer.compose_rephoto("fam-2", Lang.ES, NOW - timedelta(days=1))]
    responses = [make_response("st1", "i1"), make_response("st2", "i2")]
    grades = [make_grade("st1", "i1", True)]
    rework = BoundedAttempts(1)
    report = verify_daily(TODAY, sessions, grades, responses, quarantines, escalations, rework)
    assert (report.sessions_planned, report.sessions_delivered) == (2, 1)
    assert (report.responses_graded, report.quarantines_open) == (1, 1)
    assert report.escalations_fired == 1
    assert report.unresolved == ["ses-stuck", "st2#i2"]
    assert report.rework_attempts == 1
    assert report.pending_human == ["q1", escalations[0].id, escalations[1].id]


def test_optimizer_retires_broken_items_and_keeps_the_healthy_one():
    grades = scored_grades() + [make_grade("s0", "i-open", None)]
    active = [make_item(item_id, ItemStatus.ACTIVE) for item_id in PATTERNS]
    shelved = [make_item("i-flat", ItemStatus.CANDIDATE)]
    assert optimizer.student_totals(grades)["s0"] == pytest.approx(0.6)
    assert optimizer.retirement_candidates(active, grades, 5) == ["i-all-correct", "i-flat"]
    assert optimizer.retirement_candidates(shelved, grades, 5) == []
    assert optimizer.retire(active[0]).status is ItemStatus.RETIRED
    assert active[0].status is ItemStatus.ACTIVE


def test_regeneration_requests_stop_at_the_budget():
    budget = BoundedAttempts(1)
    requests = optimizer.regeneration_requests(["i-all-correct", "i-flat"], budget)
    assert requests == ["i-all-correct"]
    assert budget.attempts_used() == 1
    assert optimizer.regeneration_requests(["i-flat"], budget) == []
