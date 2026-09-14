from dataclasses import dataclass, field
from datetime import date, timedelta
from unicodedata import normalize

from repaso.core.harness.bloom import BLOOM_ORDER, bloom_distance
from repaso.schemas.common import CompetencyId, ItemId, Lang
from repaso.schemas.item import BloomLevel, Item, ItemKind, ItemStatus
from repaso.schemas.schedule import SpacedItemState

UNTAGGED_RANK = len(BLOOM_ORDER)
RECENT_DAYS = 2


@dataclass(frozen=True)
class BankQuery:
    competency_ids: tuple[CompetencyId, ...] = ()
    kinds: tuple[ItemKind, ...] = ()
    bloom: BloomLevel | None = None
    lang: Lang | None = None
    grade: int | None = None
    exclude: frozenset[ItemId] = field(default_factory=frozenset)
    limit: int = 3
    distinct_content: bool = False


def _tag_fits(tagged: object, wanted: object) -> bool:
    return wanted is None or tagged is None or tagged == wanted


def matches(item: Item, query: BankQuery) -> bool:
    if item.status is not ItemStatus.ACTIVE or item.variant_of is not None:
        return False
    if item.id in query.exclude:
        return False
    if query.competency_ids and item.competency_id not in query.competency_ids:
        return False
    if query.kinds and item.kind not in query.kinds:
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
    if query.distinct_content:
        seen = {question_key(item) for item in items if item.id in query.exclude}
        distinct = []
        for item in found:
            key = question_key(item)
            if key not in seen:
                distinct.append(item)
                seen.add(key)
        found = distinct
    return found[: query.limit]


def question_key(item: Item) -> tuple:
    """Display content, independent of database ID or answer-option order."""

    def text(value: str) -> str:
        return " ".join(normalize("NFKC", value).casefold().split())

    return item.kind, text(item.stem), tuple(sorted(text(option) for option in item.options))


def last_seen(state: SpacedItemState) -> date:
    return state.due_date - timedelta(days=state.interval_days)


def seen_recently(
    states: list[SpacedItemState], today: date, days: int = RECENT_DAYS
) -> frozenset[ItemId]:
    horizon = today - timedelta(days=days)
    return frozenset(state.item_id for state in states if last_seen(state) >= horizon)
