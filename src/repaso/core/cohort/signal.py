from datetime import date, timedelta

from repaso.schemas.cohort import CohortKey
from repaso.schemas.common import CompetencyId, FrozenStrictModel

CLAIM_PREFIX = "cohort"
CLAIM_SEPARATOR = "#"


class CohortFailure(FrozenStrictModel):
    family_id: str
    section_key: str
    competency_id: str
    failed_on: date


def within_window(failure: CohortFailure, window_days: int, today: date) -> bool:
    return today - timedelta(days=window_days) < failure.failed_on <= today


def group_families(
    failures: list[CohortFailure], window_days: int, today: date
) -> dict[tuple[str, str], set[str]]:
    groups: dict[tuple[str, str], set[str]] = {}
    for failure in failures:
        if not within_window(failure, window_days, today):
            continue
        group = groups.setdefault((failure.section_key, failure.competency_id), set())
        group.add(failure.family_id)
    return groups


def evaluate(
    failures: list[CohortFailure],
    min_families: int,
    window_days: int,
    today: date,
) -> list[CohortKey]:
    if min_families < 1:
        raise ValueError("min_families must be positive")
    if window_days < 1:
        raise ValueError("window_days must be positive")
    groups = group_families(failures, window_days, today)
    return [
        CohortKey(section_key=section_key, competency_id=CompetencyId(competency_id))
        for section_key, competency_id in sorted(groups)
        if len(groups[(section_key, competency_id)]) >= min_families
    ]


def signal_claim_key(key: CohortKey, today: date) -> str:
    iso_year, iso_week, _ = today.isocalendar()
    parts = (CLAIM_PREFIX, key.section_key, key.competency_id, f"{iso_year}-W{iso_week:02d}")
    return CLAIM_SEPARATOR.join(parts)
