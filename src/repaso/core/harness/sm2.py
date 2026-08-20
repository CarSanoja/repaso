from datetime import date, timedelta

from repaso.schemas.schedule import SpacedItemState

MIN_EASE = 1.3
FIRST_INTERVALS = (1, 3)
FAILURE_QUALITY_THRESHOLD = 3


def review(state: SpacedItemState, quality: int, today: date) -> SpacedItemState:
    if not 0 <= quality <= 5:
        raise ValueError("quality must be between 0 and 5")
    if quality < FAILURE_QUALITY_THRESHOLD:
        return state.model_copy(
            update={
                "repetitions": 0,
                "interval_days": 1,
                "lapses": state.lapses + 1,
                "due_date": today + timedelta(days=1),
            }
        )
    ease = max(MIN_EASE, state.ease + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    repetitions = state.repetitions + 1
    if repetitions <= len(FIRST_INTERVALS):
        interval = FIRST_INTERVALS[repetitions - 1]
    else:
        interval = max(1, round(state.interval_days * ease))
    return state.model_copy(
        update={
            "repetitions": repetitions,
            "ease": ease,
            "interval_days": interval,
            "due_date": today + timedelta(days=interval),
        }
    )


def is_due(state: SpacedItemState, today: date) -> bool:
    return state.due_date <= today


def due_items(states: list[SpacedItemState], today: date, limit: int) -> list[SpacedItemState]:
    if limit < 1:
        raise ValueError("limit must be positive")
    overdue = [state for state in states if is_due(state, today)]
    overdue.sort(key=lambda state: (state.due_date, -state.lapses, state.item_id))
    return overdue[:limit]


def grade_to_quality(correct: bool, latency_seconds: float, expected_seconds: float) -> int:
    if not correct:
        return 1
    if expected_seconds <= 0:
        return 4
    if latency_seconds <= expected_seconds:
        return 5
    if latency_seconds <= expected_seconds * 2:
        return 4
    return 3
