from datetime import UTC, date, datetime

from repaso.config.models import ModelRole
from repaso.core.orchestration.context import TutorRun
from repaso.core.orchestration.tutor_graph import build_session_graph
from repaso.schemas.item import Item, ItemKind, ItemStatus
from repaso.schemas.mastery import MasteryState
from repaso.schemas.provenance import Provenance, Source
from repaso.schemas.schedule import ExamDate, SpacedItemState
from tests.orchestration.fixtures import FRACTIONS, make_services, seed_family

START = datetime(2026, 9, 1, 19, 0, tzinfo=UTC)
TODAY = date(2026, 9, 1)
WEAK = "math.g4.division.with_remainder"
STRONG = FRACTIONS


def seed_item(store, item_id: str, competency_id: str) -> None:
    store.put_item(
        Item(
            id=item_id,
            competency_id=competency_id,
            kind=ItemKind.MCQ,
            difficulty=2,
            stem="Which fraction equals 2/4?",
            options=["1/2", "2/8", "3/4"],
            answer_key="1/2",
            rationale="both halves",
            status=ItemStatus.ACTIVE,
            provenance=Provenance(source=Source.GENERATED, created_at=START),
        )
    )


def seed_mastery(store, student_id: str, competency_id: str, ema: float) -> None:
    store.put_mastery(
        MasteryState(
            student_id=student_id,
            competency_id=competency_id,
            ema_accuracy=ema,
            attempts=10,
            correct=int(ema * 10),
        )
    )


def seed_board(services, student_id: str) -> None:
    seed_mastery(services.store, student_id, WEAK, 0.2)
    seed_mastery(services.store, student_id, STRONG, 0.9)
    seed_item(services.store, "i-strong-due", STRONG)
    seed_item(services.store, "i-weak-due", WEAK)
    seed_item(services.store, "i-strong-a", STRONG)
    seed_item(services.store, "i-strong-b", STRONG)
    seed_item(services.store, "i-weak-a", WEAK)
    services.store.put_spaced(
        SpacedItemState(student_id=student_id, item_id="i-strong-due", due_date=date(2026, 8, 30))
    )
    services.store.put_spaced(
        SpacedItemState(student_id=student_id, item_id="i-weak-due", due_date=date(2026, 8, 31))
    )


async def run_session(services, family, student) -> TutorRun:
    services.models[ModelRole.GENERATE].enqueue({"text": "Repaso de hoy..."})
    run = TutorRun(family=family, student=student)
    await build_session_graph(services, run).invoke_async("session")
    return run


async def test_without_an_exam_the_plan_keeps_its_size_and_order(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_board(services, student.id)

    run = await run_session(services, family, student)

    assert [item.id for item in run.items] == ["i-strong-due", "i-weak-due", "i-weak-a"]
    assert run.competency.id == STRONG


async def test_an_exam_within_the_horizon_adds_an_item_and_leads_with_the_weakest(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_board(services, student.id)
    services.store.put_exam_date(
        ExamDate(student_id=student.id, competency_id=None, exam_date=date(2026, 9, 4))
    )

    run = await run_session(services, family, student)

    assert len(run.items) == 4
    assert [item.competency_id for item in run.items] == [WEAK, WEAK, STRONG, STRONG]
    assert run.competency.id == WEAK
    assert set(run.session.capsule.item_ids) == {item.id for item in run.items}


async def test_the_last_day_of_the_horizon_still_counts_as_urgent(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_board(services, student.id)
    services.store.put_exam_date(
        ExamDate(student_id=student.id, competency_id=None, exam_date=date(2026, 9, 8))
    )

    run = await run_session(services, family, student)

    assert len(run.items) == 4


async def test_an_exam_past_the_horizon_leaves_the_plan_alone(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_board(services, student.id)
    services.store.put_exam_date(
        ExamDate(student_id=student.id, competency_id=None, exam_date=date(2026, 9, 9))
    )

    run = await run_session(services, family, student)

    assert [item.id for item in run.items] == ["i-strong-due", "i-weak-due", "i-weak-a"]


async def test_a_past_exam_never_reorders_the_plan(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_board(services, student.id)
    services.store.put_exam_date(
        ExamDate(student_id=student.id, competency_id=None, exam_date=date(2026, 8, 25))
    )

    run = await run_session(services, family, student)

    assert [item.id for item in run.items] == ["i-strong-due", "i-weak-due", "i-weak-a"]
