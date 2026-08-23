from statistics import fmean

from repaso.core.harness.budgets import BoundedAttempts
from repaso.core.harness.psychometrics import ItemObservation, should_retire
from repaso.schemas.grading import GradeResult
from repaso.schemas.item import Item, ItemStatus


def student_totals(grades: list[GradeResult]) -> dict[str, float]:
    outcomes: dict[str, list[float]] = {}
    for grade in grades:
        if grade.correct is None:
            continue
        outcomes.setdefault(grade.student_id, []).append(1.0 if grade.correct else 0.0)
    return {student_id: fmean(scores) for student_id, scores in outcomes.items()}


def observations(grades: list[GradeResult]) -> list[ItemObservation]:
    totals = student_totals(grades)
    return [
        ItemObservation(
            item_id=grade.item_id,
            student_id=grade.student_id,
            correct=grade.correct,
            student_total_score=totals[grade.student_id],
        )
        for grade in grades
        if grade.correct is not None and not grade.quarantined
    ]


def observations_by_item(grades: list[GradeResult]) -> dict[str, list[ItemObservation]]:
    grouped: dict[str, list[ItemObservation]] = {}
    for observation in observations(grades):
        grouped.setdefault(observation.item_id, []).append(observation)
    return grouped


def retirement_candidates(
    items: list[Item], grades: list[GradeResult], min_attempts: int
) -> list[str]:
    grouped = observations_by_item(grades)
    return sorted(
        item.id
        for item in items
        if item.status is ItemStatus.ACTIVE
        and should_retire(grouped.get(item.id, []), min_attempts)
    )


def retire(item: Item) -> Item:
    return item.model_copy(update={"status": ItemStatus.RETIRED})


def regeneration_requests(candidates: list[str], budget: BoundedAttempts) -> list[str]:
    requests: list[str] = []
    for candidate in candidates:
        if not budget.try_attempt():
            break
        requests.append(candidate)
    return requests
