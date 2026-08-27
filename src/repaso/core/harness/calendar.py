from collections.abc import Sequence
from datetime import date


def is_scheduled(
    day: date,
    rest_weekdays: Sequence[int],
    holidays: Sequence[date],
) -> bool:
    if day.weekday() in set(rest_weekdays):
        return False
    return day not in set(holidays)


def mask_to_scheduled(
    days: Sequence[date],
    counts: Sequence[int],
    rest_weekdays: Sequence[int],
    holidays: Sequence[date],
) -> list[int]:
    return [
        count
        for day, count in zip(days, counts, strict=True)
        if is_scheduled(day, rest_weekdays, holidays)
    ]
