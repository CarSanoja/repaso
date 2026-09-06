from datetime import UTC, datetime

from repaso.config.models import ModelRole
from repaso.core.orchestration.context import CloseRun
from repaso.core.orchestration.quality_graph import build_quality_graph
from repaso.schemas.grading import EvidenceSpan, GradedBy, GradeResult
from repaso.schemas.item import Item, ItemKind, ItemStatus
from repaso.schemas.mastery import MasteryLevel, MasteryState
from repaso.schemas.provenance import Provenance, Source
from tests.orchestration.fixtures import FRACTIONS, make_services, seed_family

START = datetime(2026, 9, 1, 19, 0, tzinfo=UTC)


def seed_struggling_family(services, family_id: str, chat_ref: str) -> None:
    _, student = seed_family(services.store, family_id, chat_ref)
    services.store.put_mastery(
        MasteryState(
            student_id=student.id,
            competency_id=FRACTIONS,
            ema_accuracy=0.2,
            attempts=9,
            correct=1,
            level=MasteryLevel.STRUGGLING,
        )
    )


async def test_cohort_signal_fires_once_per_section_and_week(settings):
    services = make_services(settings)
    for index in range(3):
        seed_struggling_family(services, f"f{index}", str(100 + index))
    for _ in range(3):
        note = {"text": "Estimada maestra, varias familias..."}
        services.models[ModelRole.GENERATE].enqueue(note)

    run = CloseRun()
    await build_quality_graph(services, run).invoke_async("close")

    assert len(run.cohort_fired) == 1
    assert len(run.outbound) == 1  # one shared note, not three copies
    assert all("familias" in message.text for message in run.outbound)

    rerun = CloseRun()
    await build_quality_graph(services, rerun).invoke_async("close")
    assert rerun.cohort_fired == []


async def test_cohort_stays_silent_below_the_k_floor(settings):
    services = make_services(settings)
    for index in range(2):
        seed_struggling_family(services, f"f{index}", str(100 + index))

    run = CloseRun()
    await build_quality_graph(services, run).invoke_async("close")

    assert run.cohort_fired == []
    assert services.models[ModelRole.GENERATE].calls == []


async def test_optimizer_retires_items_that_measure_nothing(settings):
    services = make_services(settings)
    for index in range(4):
        seed_family(services.store, f"f{index}", str(200 + index))
    item = Item(
        id="easy1",
        competency_id=FRACTIONS,
        kind=ItemKind.MCQ,
        difficulty=1,
        stem="1/2 equals 2/4?",
        options=["yes", "no"],
        answer_key="yes",
        rationale="trivial",
        status=ItemStatus.ACTIVE,
        provenance=Provenance(source=Source.GENERATED, created_at=START),
    )
    services.store.put_item(item)
    for index in range(8):
        services.grade_log.append(
            GradeResult(
                student_id=f"s-f{index % 4}",
                item_id="easy1",
                correct=True,
                confidence=1.0,
                graded_by=GradedBy.DETERMINISTIC,
                evidence=EvidenceSpan(quote="yes", source_ref=f"response:{index}"),
                feedback="",
                graded_at=START,
            )
        )

    run = CloseRun()
    await build_quality_graph(services, run).invoke_async("close")

    assert run.retired_items == ["easy1"]
    assert services.store.get_item("easy1").status is ItemStatus.RETIRED
    assert run.report is not None
