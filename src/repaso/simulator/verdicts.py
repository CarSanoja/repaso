from repaso.core.harness.escalation_triggers import DEFAULT_COOLDOWN_DAYS
from repaso.schemas.escalation import EscalationKind
from repaso.schemas.review import QuarantineKind
from repaso.simulator.archetypes import Archetype
from repaso.simulator.cohort import SECTION_CLUSTER
from repaso.simulator.demo_clock import DemoClockResult

Row = tuple[str, str, str, str]


def _row(case: str, expected: str, actual: str, ok: bool) -> Row:
    return (case, expected, actual, "as expected" if ok else "NOT as expected")


def _students(result: DemoClockResult, *archetypes: Archetype) -> set[str]:
    return {
        member.student.id
        for member in result.ledger.members
        if member.archetype in archetypes
    }


def verdict_rows(result: DemoClockResult) -> list[Row]:
    ledger = result.ledger
    struggle = result.escalated_students.get(EscalationKind.STRUGGLE_TRIAGE.value, set())
    engagement = result.escalated_students.get(EscalationKind.ENGAGEMENT.value, set())
    low = _students(result, Archetype.STRUGGLING, Archetype.COHORT_CLUSTER)
    disengaged = _students(result, Archetype.DISENGAGED)
    fast = _students(result, Archetype.FAST_GUESSER)
    switchers = {s for s, actions in result.decisions.items() if "switch_to_open" in actions}

    gaps_ok = True
    refires = 0
    for dates in result.struggle_fires.values():
        ordered = sorted(dates)
        refires += max(0, len(ordered) - 1)
        for earlier, later in zip(ordered, ordered[1:], strict=False):
            if (later - earlier).days < DEFAULT_COOLDOWN_DAYS:
                gaps_ok = False

    sections = {signal.split("#")[0] for signal in result.cohort_signals}
    weekly_ok = bool(result.cohort_signals) and all(
        count <= 1 for count in result.cohort_weeks.values()
    )
    injections = result.quarantines_by_kind.get(QuarantineKind.INJECTION_ATTEMPT.value, 0)
    hedged = result.quarantines_by_kind.get(QuarantineKind.LOW_CONFIDENCE_GRADE.value, 0)

    return [
        _row(
            "struggle triage reaches every low-ability student",
            str(ledger.expected_struggle_students),
            str(len(struggle & low)),
            struggle & low == low,
        ),
        _row(
            "struggle triage never fires outside the low-ability group",
            "0",
            str(len(struggle - low)),
            not (struggle - low),
        ),
        _row(
            "refires wait out the full cooldown after parent resolution",
            f">=1 refire, gaps >= {DEFAULT_COOLDOWN_DAYS}d",
            f"{refires} refires, gaps_ok={gaps_ok}",
            refires >= 1 and gaps_ok,
        ),
        _row(
            "engagement alert reaches every disengaged student",
            str(ledger.expected_engagement_students),
            str(len(engagement & disengaged)),
            engagement & disengaged == disengaged,
        ),
        _row(
            "engagement alert never fires for active students",
            "0",
            str(len(engagement - disengaged)),
            not (engagement - disengaged),
        ),
        _row(
            "cohort signal fires only for the clustered section, at most once per week",
            f"{SECTION_CLUSTER}, <=1/week",
            ",".join(sorted(sections)) or "-",
            sections == {SECTION_CLUSTER} and weekly_ok,
        ),
        _row(
            "every planted injection is intercepted, none invented",
            str(result.planted_injections),
            str(injections),
            injections == result.planted_injections and result.planted_injections >= 1,
        ),
        _row(
            "every hedged open answer quarantines, none auto-graded",
            str(result.planted_hedged),
            str(hedged),
            hedged == result.planted_hedged and result.planted_hedged >= 1,
        ),
        _row(
            "fast-guess switch fires for exactly the fast guessers",
            ",".join(sorted(fast)),
            ",".join(sorted(switchers)) or "-",
            switchers == fast,
        ),
    ]
