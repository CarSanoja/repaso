from datetime import datetime

from repaso.schemas.mastery import MasteryLevel, MasteryState

EMA_ALPHA = 0.3
MIN_ATTEMPTS_FOR_LEVEL = 3
STRUGGLING_CEILING = 0.4
DEVELOPING_CEILING = 0.65
SOLID_CEILING = 0.85


def classify(ema_accuracy: float, attempts: int) -> MasteryLevel:
    if attempts < MIN_ATTEMPTS_FOR_LEVEL:
        return MasteryLevel.UNKNOWN
    if ema_accuracy < STRUGGLING_CEILING:
        return MasteryLevel.STRUGGLING
    if ema_accuracy < DEVELOPING_CEILING:
        return MasteryLevel.DEVELOPING
    if ema_accuracy < SOLID_CEILING:
        return MasteryLevel.SOLID
    return MasteryLevel.MASTERED


def update_mastery(state: MasteryState, correct: bool, practiced_at: datetime) -> MasteryState:
    outcome = 1.0 if correct else 0.0
    prior = state.ema_accuracy if state.attempts else outcome
    ema = EMA_ALPHA * outcome + (1 - EMA_ALPHA) * prior
    attempts = state.attempts + 1
    correct_total = state.correct + (1 if correct else 0)
    streak = state.streak + 1 if correct else (state.streak - 1 if state.streak < 0 else -1)
    return state.model_copy(
        update={
            "ema_accuracy": ema,
            "attempts": attempts,
            "correct": correct_total,
            "streak": streak,
            "level": classify(ema, attempts),
            "last_practiced_at": practiced_at,
        }
    )
