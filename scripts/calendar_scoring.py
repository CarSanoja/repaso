from collections import Counter
from datetime import date, timedelta

from repaso.core.harness.calendar import is_scheduled

START = date(2026, 9, 1)
DAYS = 28
WINDOW_DAYS = 14
ONE_DAY = timedelta(days=1)
REST_WEEKDAYS = (5, 6)
CARNAVAL = (date(2026, 9, 14), date(2026, 9, 15))
SEMANA_SANTA = tuple(date(2026, 9, 21) + timedelta(days=offset) for offset in range(5))
HOLIDAYS = CARNAVAL + SEMANA_SANTA
OUTAGE = tuple(date(2026, 9, 8) + timedelta(days=offset) for offset in range(3))
DISENGAGED = "disengaged"
DROPOUT_DAY = 6
OUTAGE_DROPOUT = "stu17"
LATENCY_GATE = 3
ENGAGEMENT_FP_ROW = "engagement alert never fires for active students"
CAUSES = ("calendar", "outage", "noise")
GAPS = ("weekend", "carnaval", "semana_santa", "outage")
ARMS = {
    "flat": {"overlay": False, "mask": True, "health": True},
    "on": {"overlay": True, "mask": True, "health": True},
    "off": {"overlay": True, "mask": False, "health": False},
    "health": {"overlay": True, "mask": False, "health": True},
    "defer": {"overlay": True, "mask": True, "health": False},
}


def run_days() -> list[date]:
    return [START + timedelta(days=offset) for offset in range(DAYS)]


def school_day(day: date) -> bool:
    return is_scheduled(day, REST_WEEKDAYS, HOLIDAYS)


def silent_run(
    fired_on: date, answered: set[date], masked: bool, healthy: bool = False
) -> list[date]:
    floor = max(START, fired_on - timedelta(days=WINDOW_DAYS - 1))
    silent, day = [], fired_on
    while day >= floor:
        if (masked and not school_day(day)) or (healthy and day in OUTAGE):
            day -= ONE_DAY
            continue
        if day in answered:
            break
        silent.append(day)
        day -= ONE_DAY
    return silent


def gaps_in(silent: list[date]) -> list[str]:
    kinds = set()
    for day in silent:
        if day in OUTAGE:
            kinds.add("outage")
        if day in CARNAVAL:
            kinds.add("carnaval")
        elif day in SEMANA_SANTA:
            kinds.add("semana_santa")
        elif day.weekday() in REST_WEEKDAYS:
            kinds.add("weekend")
    return sorted(kinds)


def cause_of(silent: list[date], overlay: bool) -> str:
    if not overlay:
        return "noise"
    if any(not school_day(day) for day in silent):
        return "calendar"
    if any(day in OUTAGE for day in silent):
        return "outage"
    return "noise"


def clean_runs(runs: list[dict]) -> int:
    return sum(1 for run in runs if not run["false_alerts"])


def runs_without_calendar_alerts(runs: list[dict]) -> int:
    return sum(
        1
        for run in runs
        if not [alert for alert in run["false_alerts"] if alert["cause"] == "calendar"]
    )


def runs_catching_every_dropout(runs: list[dict]) -> int:
    return sum(
        1
        for run in runs
        if len(run["detections"]) == run["dropouts"]
        and all(found["latency"] <= LATENCY_GATE for found in run["detections"])
    )


def runs_catching_the_outage_dropout(runs: list[dict]) -> int:
    return sum(
        1
        for run in runs
        if any(
            found["student"] == OUTAGE_DROPOUT and found["latency"] <= LATENCY_GATE
            for found in run["detections"]
        )
    )


def gate_line(name: str, threshold: str, passed: int, total: int, floor: float) -> str:
    verdict = "passed" if total and passed / total >= floor else "FAILED"
    return f"{name:56} {threshold:>18} {passed:>2}/{total:<2} {verdict}"


def alert_line(arm: str, runs: list[dict], student_weeks: float) -> str:
    alerts = [alert for run in runs for alert in run["false_alerts"]]
    causes = Counter(alert["cause"] for alert in alerts)
    students = len(
        {(run["seed"], alert["student"]) for run in runs for alert in run["false_alerts"]}
    )
    split = "".join(f"{causes.get(cause, 0):>10}" for cause in CAUSES)
    return (
        f"{arm:>6}{len(alerts):>8}{students:>10}{len(alerts) / len(runs):>9.1f}"
        f"{100 * len(alerts) / student_weeks:>10.1f}{split}"
    )


def latency_line(arm: str, runs: list[dict]) -> str:
    found = [detection["latency"] for run in runs for detection in run["detections"]]
    missed = sum(run["dropouts"] for run in runs) - len(found)
    spread = Counter(found)
    columns = "".join(f"{spread.get(latency, 0):>6}" for latency in (0, 1, 2, 3))
    late = sum(count for latency, count in spread.items() if latency > LATENCY_GATE)
    school = [detection["school_days"] for run in runs for detection in run["detections"]]
    calendar = [detection["calendar_days"] for run in runs for detection in run["detections"]]
    means = f"{_mean(school):>9.1f}{_mean(calendar):>10.1f}"
    return f"{arm:>6}{len(found):>6}{columns}{late:>6}{missed:>8}{means}"


def health_line(arm: str, runs: list[dict]) -> str:
    flagged = [date.fromisoformat(day) for run in runs for day in run["health_days"]]
    kinds = Counter(kind for day in flagged for kind in gaps_in([day]))
    split = "".join(f"{kinds.get(kind, 0):>13}" for kind in GAPS)
    same = len({tuple(run["health_days"]) for run in runs}) == 1
    return f"{arm:>6}{len(flagged) / len(runs):>9.1f}{split}{'yes' if same else 'no':>8}"


def _mean(values: list[int]) -> float:
    return sum(values) / len(values) if values else 0.0
