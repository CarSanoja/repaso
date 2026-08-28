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
LATENCY_GATE = 3
ENGAGEMENT_FP_ROW = "engagement alert never fires for active students"
CAUSES = ("calendar", "outage", "noise")
GAPS = ("weekend", "carnaval", "semana_santa", "outage")
ARMS = {
    "flat": {"overlay": False, "mask": True},
    "on": {"overlay": True, "mask": True},
    "off": {"overlay": True, "mask": False},
}


def school_day(day: date) -> bool:
    return is_scheduled(day, REST_WEEKDAYS, HOLIDAYS)


def silent_run(fired_on: date, answered: set[date], masked: bool) -> list[date]:
    floor = max(START, fired_on - timedelta(days=WINDOW_DAYS - 1))
    silent, day = [], fired_on
    while day >= floor:
        if masked and not school_day(day):
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
        f"{arm:>4}{len(alerts):>8}{students:>10}{len(alerts) / len(runs):>9.1f}"
        f"{100 * len(alerts) / student_weeks:>10.1f}{split}"
    )


def latency_line(arm: str, runs: list[dict]) -> str:
    found = [detection["latency"] for run in runs for detection in run["detections"]]
    missed = sum(run["dropouts"] for run in runs) - len(found)
    spread = Counter(found)
    columns = "".join(f"{spread.get(latency, 0):>6}" for latency in (1, 2, 3))
    late = sum(count for latency, count in spread.items() if latency > LATENCY_GATE)
    return f"{arm:>4}{len(found):>6}{columns}{late:>6}{missed:>8}"


def fires_by_date(runs: list[dict]) -> Counter:
    return Counter(alert["fired_on"] for run in runs for alert in run["false_alerts"])


def print_report(arms: dict[str, list[dict]], seeds: int, elapsed: float) -> None:
    on, off = arms["on"], arms["off"]
    students = on[0]["students"]
    student_weeks = seeds * students * DAYS / 7
    print(f"calendar bench: {seeds} held-out seeds x {len(arms)} arms x {DAYS} days x {students}"
          f" students = {len(arms) * seeds * students * DAYS:,} student-days"
          f" ({student_weeks:,.0f} student-weeks per arm) in {elapsed:.0f}s")
    for arm, runs in arms.items():
        print(f"  {arm:>4}: {runs[0]['scheduled_days']:>2} scheduled days,"
              f" {runs[0]['sessions_delivered']:>3} sessions, {runs[0]['responses']:>4} responses")

    print()
    print(gate_line("A  masking ON, zero false alerts per run", ">= 95% of seeds",
                    clean_runs(on), len(on), 0.95))
    print(gate_line("A2 masking ON, zero calendar-caused false alerts", "100% of seeds",
                    runs_without_calendar_alerts(on), len(on), 1.0))
    print(gate_line(f"B  every dropout alerted <= {LATENCY_GATE} scheduled days",
                    ">= 90% of seeds", runs_catching_every_dropout(on), len(on), 0.90))
    print(gate_line("C  masking OFF still fires false alerts", "majority of seeds",
                    len(off) - clean_runs(off), len(off), 0.51))

    header = "".join(f"{cause:>10}" for cause in CAUSES)
    print(f"\nfalse engagement alerts on non-disengaged students"
          f"\n{'arm':>4}{'total':>8}{'students':>10}{'per run':>9}{'per 100sw':>10}{header}")
    for arm, runs in arms.items():
        print(alert_line(arm, runs, student_weeks))

    print(f"\nfalse alerts whose silent run touches each gap type (an alert can touch several)"
          f"\n{'gap':>13}{'flat':>7}{'on':>7}{'off':>7}{'off/100sw':>11}")
    for gap in GAPS:
        counts = [
            sum(1 for run in arms[arm] for alert in run["false_alerts"] if gap in alert["gaps"])
            for arm in ARMS
        ]
        cells = "".join(f"{count:>7}" for count in counts)
        print(f"{gap:>13}{cells}{100 * counts[-1] / student_weeks:>11.1f}")

    print(f"\ndropout detection latency, scheduled days after the last response"
          f"\n{'arm':>4}{'found':>6}{'1':>6}{'2':>6}{'3':>6}{'>3':>6}{'missed':>8}")
    for arm, runs in arms.items():
        print(latency_line(arm, runs))

    print(f"\nfalse alerts by fire date\n{'date':>12}{'flat':>7}{'on':>7}{'off':>7}")
    counted = {arm: fires_by_date(runs) for arm, runs in arms.items()}
    for fired_on in sorted(set().union(*[set(dates) for dates in counted.values()])):
        cells = "".join(f"{counted[arm].get(fired_on, 0):>7}" for arm in ARMS)
        print(f"{fired_on:>12}{cells}")

    print(f"\n{'ledger verdict':64}{'flat':>7}{'on':>7}{'off':>7}")
    for case in on[0]["verdicts"]:
        cells = "".join(
            f"{sum(1 for run in arms[arm] if run['verdicts'][case]):>4}/{seeds:<3}"
            for arm in ARMS
        )
        print(f"{case:64}{cells}")
    rows = [case for case in on[0]["verdicts"] if case != ENGAGEMENT_FP_ROW]
    identical = sum(
        1
        for left, right in zip(on, off, strict=True)
        for case in rows
        if left["verdicts"][case] == right["verdicts"][case]
    )
    print(f"\nnon-engagement ledger rows identical between masking ON and OFF:"
          f" {identical}/{len(rows) * len(on)} seed-rows")
