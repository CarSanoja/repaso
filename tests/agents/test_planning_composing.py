from datetime import UTC, date, datetime

from repaso.agents.capsule_composer import Snippet, answer_ref, compose_capsule, render_item
from repaso.agents.session_planner import DAILY_ITEM_LIMIT, build_session, plan_items
from repaso.core.harness.clock import SimClock
from repaso.schemas.channel import ChannelKind
from repaso.schemas.common import Lang
from repaso.schemas.competency import Competency
from repaso.schemas.grading import EvidenceSpan, GradedBy, GradeResult
from repaso.schemas.item import Item, ItemKind, ItemStatus
from repaso.schemas.mastery import MasteryState
from repaso.schemas.provenance import Provenance, Source
from repaso.schemas.schedule import SpacedItemState
from repaso.schemas.session import PracticeSession, SessionStatus
from repaso.tools.grade_log import LocalGradeLog, build_grade_log
from repaso.tools.llm import LocalPlaybackModel

NOW = datetime(2026, 9, 1, 19, 0, tzinfo=UTC)
TODAY = date(2026, 9, 1)
PROVENANCE = Provenance(source=Source.GENERATED, created_at=NOW)
FRACTIONS = Competency(
    id="c1",
    subject="matematica",
    grade=4,
    name="Fracciones equivalentes",
    description="Reconocer fracciones que valen lo mismo.",
)


class BrokenModel:
    def structured_output(self, output_model, prompt, system_prompt=None):
        async def failing():
            raise RuntimeError("boom")
            yield {}

        return failing()


def make_item(item_id: str, competency_id: str = "c1", kind=ItemKind.MCQ) -> Item:
    options = ["1/2", "2/4", "3/4"] if kind is ItemKind.MCQ else []
    return Item(
        id=item_id,
        competency_id=competency_id,
        kind=kind,
        difficulty=2,
        stem="¿Cuál equivale a 2/4?",
        options=options,
        answer_key="1/2",
        rationale="Se simplifica dividiendo entre dos.",
        rubric=None if kind is ItemKind.MCQ else "Menciona la simplificación.",
        status=ItemStatus.ACTIVE,
        provenance=PROVENANCE,
    )


def spaced(item_id: str, due: date) -> SpacedItemState:
    return SpacedItemState(student_id="s1", item_id=item_id, due_date=due)


def mastery(competency_id: str, ema: float) -> MasteryState:
    return MasteryState(
        student_id="s1", competency_id=competency_id, ema_accuracy=ema, attempts=6, correct=3
    )


def grade(item_id: str, student_id: str = "s1", correct: bool = True) -> GradeResult:
    return GradeResult(
        student_id=student_id,
        item_id=item_id,
        correct=correct,
        confidence=0.95,
        graded_by=GradedBy.DETERMINISTIC,
        evidence=EvidenceSpan(quote="1/2", source_ref=item_id),
        feedback="Bien hecho.",
        graded_at=NOW,
    )


SESSION = build_session("s1", TODAY, ["i1", "i2"], "sess-1")


def test_plan_takes_due_items_first_then_the_weakest_competency():
    states = [spaced("i1", TODAY), spaced("i2", date(2026, 9, 5))]
    items = [make_item("i1"), make_item("i2"), make_item("i3", "c2"), make_item("i4", "c3")]
    items.append(make_item("i5", "c4"))

    planned = plan_items(states, [mastery("c2", 0.9), mastery("c3", 0.2)], items, TODAY)

    assert planned == ["i1", "i4", "i5"]


def test_plan_breaks_ema_ties_by_item_id():
    items = [make_item("i9", "c2"), make_item("i3", "c3"), make_item("i7", "c2")]

    planned = plan_items([], [mastery("c2", 0.4), mastery("c3", 0.4)], items, TODAY, limit=2)

    assert planned == ["i3", "i7"]


def test_plan_never_exceeds_the_limit_or_repeats_an_id():
    states = [spaced("i1", TODAY), spaced("i2", TODAY), spaced("i3", TODAY), spaced("i4", TODAY)]
    items = [make_item(f"i{n}") for n in range(1, 7)]

    planned = plan_items(states, [], items, TODAY)

    assert len(planned) == len(set(planned)) == DAILY_ITEM_LIMIT
    due_picked = [i for i in planned if i in {"i1", "i2", "i3", "i4"}]
    unseen_picked = [i for i in planned if i in {"i5", "i6"}]
    assert len(due_picked) == DAILY_ITEM_LIMIT - 1
    assert len(unseen_picked) == 1


def test_plan_returns_nothing_when_nothing_is_due_and_nothing_is_unseen():
    states = [spaced("i1", date(2026, 9, 4))]

    assert plan_items(states, [mastery("c1", 0.3)], [make_item("i1")], TODAY) == []


def test_build_session_starts_planned_without_a_capsule():
    assert SESSION == PracticeSession(
        id="sess-1",
        student_id="s1",
        session_date=TODAY,
        status=SessionStatus.PLANNED,
        planned_item_ids=["i1", "i2"],
    )
    assert SESSION.capsule is None


async def test_capsule_message_carries_header_snippet_and_first_item():
    model = LocalPlaybackModel([{"text": "Dos fracciones equivalen cuando valen lo mismo."}])
    items = [make_item("i1"), make_item("i2")]

    capsule, message = await compose_capsule(SESSION, items, FRACTIONS, "Leo", Lang.ES, model)

    assert capsule.item_ids == ["i1", "i2"]
    assert capsule.concept_snippet == "Dos fracciones equivalen cuando valen lo mismo."
    assert message.text == (
        "Práctica de hoy para Leo — Fracciones equivalentes\n\n"
        "Dos fracciones equivalen cuando valen lo mismo.\n\n"
        "¿Cuál equivale a 2/4?\n1. 1/2\n2. 2/4\n3. 3/4"
    )
    assert message.channel is ChannelKind.TELEGRAM
    assert message.chat_ref == ""


async def test_buttons_carry_one_based_callback_data():
    model = LocalPlaybackModel([Snippet(text="Repasa las fracciones.")])

    _, message = await compose_capsule(SESSION, [make_item("i1")], FRACTIONS, "Leo", Lang.ES, model)

    assert [button.label for button in message.buttons] == ["1/2", "2/4", "3/4"]
    assert [button.callback_data for button in message.buttons] == [
        *[f"ans:{answer_ref(SESSION.id, 'i1')}:{n}" for n in range(1, 4)],
    ]


async def test_open_item_produces_no_buttons():
    model = LocalPlaybackModel([{"text": "Explica con tus palabras."}])
    item = make_item("i1", kind=ItemKind.OPEN)

    _, message = await compose_capsule(SESSION, [item], FRACTIONS, "Leo", Lang.ES, model)

    assert message.buttons == []
    assert message.text.endswith("¿Cuál equivale a 2/4?")
    assert render_item(item) == "¿Cuál equivale a 2/4?"


async def test_broken_model_falls_back_to_a_reminder_in_the_family_language():
    items = [make_item("i1")]
    model = BrokenModel()

    capsule, message = await compose_capsule(SESSION, items, FRACTIONS, "Leo", Lang.ES, model)

    assert (
        capsule.concept_snippet
        == "Hoy practicamos Fracciones equivalentes. Lee cada pregunta con calma."
    )
    assert capsule.concept_snippet in message.text


def test_grade_log_round_trips_by_item_and_by_student(tmp_path):
    log = LocalGradeLog(tmp_path / "state", SimClock(NOW))
    log.append(grade("i1"))
    log.append(grade("i1", student_id="s2", correct=False))
    log.append(grade("i2"))

    assert [result.item_id for result in log.by_item("i1")] == ["i1", "i1"]
    assert log.by_student("s1") == [grade("i1"), grade("i2")]
    assert log.by_item("i9") == [] and log.by_student("s9") == []


def test_grades_survive_a_fresh_log_on_the_same_directory(tmp_path):
    LocalGradeLog(tmp_path / "state").append(grade("i1"))
    second = LocalGradeLog(tmp_path / "state")
    second.append(grade("i2"))

    assert [result.item_id for result in second.by_student("s1")] == ["i1", "i2"]
    assert [result.item_id for result in LocalGradeLog(tmp_path / "state").by_item("i2")] == ["i2"]


def test_build_grade_log_writes_under_the_local_state_directory(settings):
    log = build_grade_log(settings, SimClock(NOW))
    log.append(grade("i1"))

    assert isinstance(log, LocalGradeLog)
    assert log.path == settings.local_data_dir / "state" / "grades.jsonl"
    assert log.by_student("s1") == [grade("i1")]
