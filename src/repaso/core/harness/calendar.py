from collections.abc import Sequence
from datetime import date
from statistics import median

OUTAGE_COLLAPSE_RATIO = 0.2
OUTAGE_BASELINE_DAYS = 7


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


def outage_days(
    daily_totals: dict[date, int],
    scheduled: Sequence[date],
    collapse_ratio: float = OUTAGE_COLLAPSE_RATIO,
    baseline_window: int = OUTAGE_BASELINE_DAYS,
) -> set[date]:
    collapsed: set[date] = set()
    baseline: list[int] = []
    for day in sorted(scheduled):
        total = daily_totals.get(day, 0)
        if baseline and total < collapse_ratio * median(baseline[-baseline_window:]):
            collapsed.add(day)
        elif total > 0:
            baseline.append(total)
    return collapsed
