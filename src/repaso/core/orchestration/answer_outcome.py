from repaso.core.harness.mastery import update_mastery
from repaso.core.harness.sm2 import grade_to_quality, review
from repaso.core.orchestration.context import Services
from repaso.schemas.common import StudentId
from repaso.schemas.item import Item
from repaso.schemas.mastery import MasteryState
from repaso.schemas.schedule import SpacedItemState

EXPECTED_ANSWER_SECONDS = 45.0


def record_answer_outcome(
    services: Services,
    student_id: StudentId,
    item: Item,
    correct: bool,
    latency_seconds: float,
) -> None:
    mastery = services.store.get_mastery(student_id, item.competency_id) or MasteryState(
        student_id=student_id,
        competency_id=item.competency_id,
        ema_accuracy=0.0,
        attempts=0,
        correct=0,
    )
    services.store.put_mastery(update_mastery(mastery, correct, services.clock.now()))
    today = services.clock.today()
    spaced = {state.item_id: state for state in services.store.list_spaced(student_id)}
    state = spaced.get(item.id) or SpacedItemState(
        student_id=student_id, item_id=item.id, due_date=today
    )
    quality = grade_to_quality(correct, latency_seconds, EXPECTED_ANSWER_SECONDS)
    services.store.put_spaced(review(state, quality, today))
