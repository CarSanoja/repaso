from dataclasses import dataclass, field
from datetime import date, timedelta

from repaso.core.harness.bloom import BLOOM_ORDER, bloom_distance
from repaso.schemas.common import CompetencyId, ItemId, Lang
from repaso.schemas.item import BloomLevel, Item, ItemStatus
from repaso.schemas.schedule import SpacedItemState

UNTAGGED_RANK = len(BLOOM_ORDER)
RECENT_DAYS = 2


@dataclass(frozen=True)
class BankQuery:
    competency_ids: tuple[CompetencyId, ...] = ()
    bloom: BloomLevel | None = None
    lang: Lang | None = None
    grade: int | None = None
    exclude: frozenset[ItemId] = field(default_factory=frozenset)
    limit: int = 3


def _tag_fits(tagged: object, wanted: object) -> bool:
    return wanted is None or tagged is None or tagged == wanted


def matches(item: Item, query: BankQuery) -> bool:
    if item.status is not ItemStatus.ACTIVE or item.variant_of is not None:
        return False
    if item.id in query.exclude:
        return False
    if query.competency_ids and item.competency_id not in query.competency_ids:
        return False
    return _tag_fits(item.lang, query.lang) and _tag_fits(item.grade, query.grade)


def level_rank(item: Item, wanted: BloomLevel | None) -> int:
    if wanted is None:
        return 0
    if item.bloom is None:
        return UNTAGGED_RANK
    return bloom_distance(item.bloom, wanted)


def at_level(items: list[Item], bloom: BloomLevel) -> list[Item]:
    return [item for item in items if item.bloom is bloom]


def _order(item: Item, query: BankQuery) -> tuple:
    return (level_rank(item, query.bloom), item.difficulty, item.id)


def query_bank(items: list[Item], query: BankQuery) -> list[Item]:
    if query.limit < 1:
        return []
    found = [item for item in items if matches(item, query)]
    found.sort(key=lambda item: _order(item, query))
    return found[: query.limit]


def last_seen(state: SpacedItemState) -> date:
    return state.due_date - timedelta(days=state.interval_days)


def seen_recently(
    states: list[SpacedItemState], today: date, days: int = RECENT_DAYS
) -> frozenset[ItemId]:
    horizon = today - timedelta(days=days)
    return frozenset(state.item_id for state in states if last_seen(state) >= horizon)
