from datetime import date

from repaso.core.harness.sm2 import due_items
from repaso.schemas.common import SessionId, StudentId
from repaso.schemas.item import Item, ItemStatus
from repaso.schemas.mastery import MasteryState
from repaso.schemas.schedule import SpacedItemState
from repaso.schemas.session import PracticeSession, SessionStatus

DAILY_ITEM_LIMIT = 3
NEW_ITEM_RESERVE = 1
UNKNOWN_EMA = 0.5


def plan_items(
    spaced_states: list[SpacedItemState],
    mastery_states: list[MasteryState],
    active_items: list[Item],
    today: date,
    limit: int = DAILY_ITEM_LIMIT,
) -> list[str]:
    if limit < 1:
        return []
    unseen = _weakest_unseen(spaced_states, mastery_states, active_items, limit)
    due_limit = max(1, limit - NEW_ITEM_RESERVE) if unseen else limit
    planned = [state.item_id for state in due_items(spaced_states, today, due_limit)]
    remaining = limit - len(planned)
    if remaining < 1:
        return planned
    return planned + unseen[:remaining]


def _weakest_unseen(
    spaced_states: list[SpacedItemState],
    mastery_states: list[MasteryState],
    active_items: list[Item],
    remaining: int,
) -> list[str]:
    seen = {state.item_id for state in spaced_states}
    ema = {state.competency_id: state.ema_accuracy for state in mastery_states}
    unseen = [
        item for item in active_items if item.id not in seen and item.status is ItemStatus.ACTIVE
    ]
    unseen.sort(key=lambda item: (ema.get(item.competency_id, UNKNOWN_EMA), item.id))
    return [item.id for item in unseen[:remaining]]


def build_session(
    student_id: str, session_date: date, item_ids: list[str], session_id: str
) -> PracticeSession:
    return PracticeSession(
        id=SessionId(session_id),
        student_id=StudentId(student_id),
        session_date=session_date,
        capsule=None,
        status=SessionStatus.PLANNED,
    )
