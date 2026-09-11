from typing import Any

from repaso.config.models import ModelRole
from repaso.core.orchestration.context import Services
from repaso.schemas.item import Item, ItemKind, ItemStatus
from repaso.simulator.demo_stage import Stage
from repaso.tools.grade_log import effective_grades

COMPETENCY = "math.g4.fractions.equivalence"
NOT_YET = "—"
HELD = "held"
ANSWERS_EXPECTED = 3
DROPPED_EXPECTED = 6


def _queue_counters(services: Services) -> list[Any]:
    counters = [getattr(model, "remaining_total", None) for model in services.models.values()]
    return [counter for counter in counters if counter is not None]


def cassette_roles(services: Services) -> int:
    return len(_queue_counters(services))


def cassette_remaining(services: Services) -> int:
    return sum(counter() for counter in _queue_counters(services))


def item_shape(items: list[Item]) -> str:
    mcq = sum(1 for item in items if item.kind is ItemKind.MCQ)
    return f"{mcq} mcq + {len(items) - mcq} open"


def harness_reading(
    stage: Stage, family: Any, student: Any, item_id: str | None, summary: dict[str, Any]
) -> tuple[tuple[str, str], ...]:
    services = stage.services
    mastery = services.store.get_mastery(student.id, COMPETENCY)
    spaced = {state.item_id: state for state in services.store.list_spaced(student.id)}
    state = spaced.get(item_id) if item_id else None
    tutor = summary.get("tutor") or {}
    return (
        ("mastery EMA", f"{mastery.ema_accuracy:.2f}" if mastery else NOT_YET),
        ("attempts", str(mastery.attempts) if mastery else "0"),
        ("level", mastery.level.value if mastery else NOT_YET),
        ("next review", f"in {state.interval_days}d" if state else HELD),
        ("decision", tutor.get("decision_action") or NOT_YET),
        ("escalations open", str(len(services.store.list_pending_escalations(family.id)))),
    )


def close_ledger(stage: Stage, family: Any, student: Any) -> None:
    services = stage.services
    rejected = services.store.list_items_by_competency(COMPETENCY, ItemStatus.REJECTED)
    mastery = services.store.get_mastery(student.id, COMPETENCY)
    graded = effective_grades(services.grade_log.by_student(student.id))
    session = services.store.get_session_by_date(student.id, services.clock.today())
    asked = [services.store.get_item(i) for i in session.capsule.item_ids]
    stage.beat("what the child was asked", "1 mcq + 2 open", item_shape(asked))
    stage.beat("questions the review dropped", DROPPED_EXPECTED, len(rejected))
    stage.beat("answers graded", ANSWERS_EXPECTED, len(graded))
    stage.beat(
        "the day ends one right, two wrong",
        "3 attempts / 1 correct",
        f"{mastery.attempts} attempts / {mastery.correct} correct" if mastery else "no mastery",
    )
    stage.beat("nobody was paged", 0, len(services.store.list_escalations(family.id)))
    stage.beat("every runtime invocation was accepted", 0, len(stage.rejected))
    stage.beat("roles played from the cassette", len(ModelRole), cassette_roles(services))
    stage.beat("cassette entries left unplayed", 0, cassette_remaining(services))
