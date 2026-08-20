from statistics import median

from repaso.schemas.mastery import MasteryLevel, MasteryState

DEFAULT_COOLDOWN_DAYS = 7
DEFAULT_SILENT_DAYS = 3
DEFAULT_MIN_ACTIVE_DAYS = 2
FAST_GUESS_RATIO = 0.25


def struggle_trigger(
    state: MasteryState,
    min_samples: int,
    last_escalated_days_ago: int | None,
    cooldown_days: int,
) -> bool:
    if state.level is not MasteryLevel.STRUGGLING:
        return False
    if state.attempts < min_samples:
        return False
    return last_escalated_days_ago is None or last_escalated_days_ago >= cooldown_days


def trailing_silent_days(daily_response_counts: list[int]) -> int:
    silent = 0
    for count in reversed(daily_response_counts):
        if count > 0:
            break
        silent += 1
    return silent


def engagement_trigger(
    daily_response_counts: list[int],
    min_active_days: int,
    silent_days_threshold: int,
) -> bool:
    active_days = sum(1 for count in daily_response_counts if count > 0)
    if active_days < min_active_days:
        return False
    return trailing_silent_days(daily_response_counts) >= silent_days_threshold


def fast_guess_flag(
    latencies_seconds: list[float],
    expected_seconds: float,
    min_samples: int,
) -> bool:
    if not latencies_seconds or len(latencies_seconds) < min_samples:
        return False
    return median(latencies_seconds) < expected_seconds * FAST_GUESS_RATIO


def streak_slope(daily_response_counts: list[int]) -> float:
    days = len(daily_response_counts)
    if days < 2:
        return 0.0
    mean_index = (days - 1) / 2
    mean_count = sum(daily_response_counts) / days
    covariance = sum(
        (index - mean_index) * (count - mean_count)
        for index, count in enumerate(daily_response_counts)
    )
    variance = sum((index - mean_index) ** 2 for index in range(days))
    return covariance / variance
