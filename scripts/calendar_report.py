from collections import Counter

from calendar_scoring import (
    ARMS,
    CAUSES,
    DAYS,
    ENGAGEMENT_FP_ROW,
    GAPS,
    LATENCY_GATE,
    alert_line,
    clean_runs,
    gate_line,
    health_line,
    latency_line,
    runs_catching_every_dropout,
    runs_catching_the_outage_dropout,
    runs_without_calendar_alerts,
)


def fires_by_date(runs: list[dict]) -> Counter:
    return Counter(alert["fired_on"] for run in runs for alert in run["false_alerts"])


def _gates(arms: dict[str, list[dict]]) -> None:
    on, off = arms["on"], arms["off"]
    print(gate_line("A  masking+health ON, zero false alerts per run", ">= 95% of seeds",
                    clean_runs(on), len(on), 0.95))
    print(gate_line("A2 masking+health ON, zero calendar-caused false alerts", "100% of seeds",
                    runs_without_calendar_alerts(on), len(on), 1.0))
    print(gate_line(f"B  every dropout alerted <= {LATENCY_GATE} scheduled days",
                    ">= 90% of seeds", runs_catching_every_dropout(on), len(on), 0.90))
    print(gate_line("C  pre-fix arm still fires false alerts", "majority of seeds",
                    len(off) - clean_runs(off), len(off), 0.51))
    print(gate_line("D  the outage-onset dropout is still caught", "100% of seeds",
                    runs_catching_the_outage_dropout(on), len(on), 1.0))


def print_report(arms: dict[str, list[dict]], seeds: int, elapsed: float) -> None:
    on, off = arms["on"], arms["off"]
    students = on[0]["students"]
    student_weeks = seeds * students * DAYS / 7
    columns = "".join(f"{arm:>9}" for arm in arms)
    print(f"calendar bench: {seeds} held-out seeds x {len(arms)} arms x {DAYS} days x {students}"
          f" students = {len(arms) * seeds * students * DAYS:,} student-days"
          f" ({student_weeks:,.0f} student-weeks per arm) in {elapsed:.0f}s")
    for arm, runs in arms.items():
        print(f"  {arm:>6}: {runs[0]['scheduled_days']:>2} scheduled days,"
              f" {runs[0]['sessions_delivered']:>3} sessions, {runs[0]['responses']:>4} responses")

    print()
    _gates(arms)

    header = "".join(f"{cause:>10}" for cause in CAUSES)
    print(f"\nfalse engagement alerts on non-disengaged students"
          f"\n{'arm':>6}{'total':>8}{'students':>10}{'per run':>9}{'per 100sw':>10}{header}")
    for arm, runs in arms.items():
        print(alert_line(arm, runs, student_weeks))

    print(f"\nfalse alerts whose calendar-day silence touches each gap (an alert can touch several)"
          f"\n{'gap':>13}{columns}{'off/100sw':>11}")
    for gap in GAPS:
        counts = [
            sum(1 for run in arms[arm] for alert in run["false_alerts"] if gap in alert["gaps"])
            for arm in ARMS
        ]
        cells = "".join(f"{count:>9}" for count in counts)
        print(f"{gap:>13}{cells}{100 * counts[2] / student_weeks:>11.1f}")

    print(f"\ndropout detection latency after the last response, in days the cohort could practice"
          f"\n{'arm':>6}{'found':>6}{'0':>6}{'1':>6}{'2':>6}{'3':>6}{'>3':>6}{'missed':>8}"
          f"{'school':>9}{'calendar':>10}")
    for arm, runs in arms.items():
        print(latency_line(arm, runs))

    print(f"\ndelivery-health: days masked as an outage, reconstructed from the finished grade log"
          f"\n{'arm':>6}{'per run':>9}" + "".join(f"{gap:>13}" for gap in GAPS) + f"{'stable':>8}")
    for arm, runs in arms.items():
        print(health_line(arm, runs))

    print(f"\nfalse alerts by fire date\n{'date':>12}{columns}")
    counted = {arm: fires_by_date(runs) for arm, runs in arms.items()}
    for fired_on in sorted(set().union(*[set(dates) for dates in counted.values()])):
        cells = "".join(f"{counted[arm].get(fired_on, 0):>9}" for arm in ARMS)
        print(f"{fired_on:>12}{cells}")

    print(f"\n{'ledger verdict':60}{columns}")
    for case in on[0]["verdicts"]:
        cells = "".join(
            f"{sum(1 for run in arms[arm] if run['verdicts'][case]):>5}/{seeds:<3}"
            for arm in ARMS
        )
        print(f"{case:60}{cells}")
    rows = [case for case in on[0]["verdicts"] if case != ENGAGEMENT_FP_ROW]
    identical = sum(
        1
        for left, right in zip(on, off, strict=True)
        for case in rows
        if left["verdicts"][case] == right["verdicts"][case]
    )
    print(f"\nnon-engagement ledger rows identical between the fixed and pre-fix arms:"
          f" {identical}/{len(rows) * len(on)} seed-rows")
