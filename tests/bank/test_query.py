from datetime import date

from repaso.core.bank.query import (
    BankQuery,
    at_level,
    last_seen,
    query_bank,
    seen_recently,
)
from repaso.schemas.common import Lang
from repaso.schemas.item import BloomLevel, ItemStatus
from repaso.schemas.schedule import SpacedItemState
from tests.bank.items import DECIMALS, make_item

TODAY = date(2026, 9, 14)


def test_a_query_returns_only_the_competency_that_was_asked_for():
    items = [make_item("a"), make_item("b", competency_id=DECIMALS)]
    found = query_bank(items, BankQuery(competency_ids=(DECIMALS,), limit=5))
    assert [item.id for item in found] == ["b"]


def test_the_level_asked_for_comes_first_and_a_neighbour_comes_before_a_stranger():
    items = [
        make_item("far", bloom=BloomLevel.REMEMBER),
        make_item("exact", bloom=BloomLevel.ANALYZE),
        make_item("near", bloom=BloomLevel.APPLY),
    ]
    found = query_bank(items, BankQuery(bloom=BloomLevel.ANALYZE, limit=3))
    assert [item.id for item in found] == ["exact", "near", "far"]


def test_an_untagged_item_is_served_last_and_never_counted_at_a_level():
    items = [make_item("untagged", bloom=None), make_item("tagged", bloom=BloomLevel.REMEMBER)]
    found = query_bank(items, BankQuery(bloom=BloomLevel.APPLY, limit=2))
    assert [item.id for item in found] == ["tagged", "untagged"]
    assert at_level(items, BloomLevel.APPLY) == []


def test_what_the_child_saw_recently_is_excluded():
    items = [make_item("a"), make_item("b")]
    found = query_bank(items, BankQuery(exclude=frozenset({"a"}), limit=5))
    assert [item.id for item in found] == ["b"]


def test_a_retired_or_rejected_item_is_never_served():
    items = [
        make_item("rejected", status=ItemStatus.REJECTED),
        make_item("candidate", status=ItemStatus.CANDIDATE),
        make_item("retired", status=ItemStatus.RETIRED),
        make_item("active"),
    ]
    found = query_bank(items, BankQuery(limit=5))
    assert [item.id for item in found] == ["active"]


def test_an_adapted_variant_is_not_a_bank_item():
    items = [make_item("variant", variant_of="a"), make_item("a")]
    found = query_bank(items, BankQuery(limit=5))
    assert [item.id for item in found] == ["a"]


def test_a_tagged_item_from_another_language_or_grade_is_refused():
    items = [
        make_item("english", lang=Lang.EN),
        make_item("fifth", grade=5),
        make_item("ours"),
    ]
    found = query_bank(items, BankQuery(lang=Lang.ES, grade=4, limit=5))
    assert [item.id for item in found] == ["ours"]


def test_an_item_stored_before_the_tags_existed_is_still_usable():
    items = [make_item("legacy", lang=None, grade=None, bloom=None)]
    found = query_bank(items, BankQuery(lang=Lang.ES, grade=4, limit=5))
    assert [item.id for item in found] == ["legacy"]


def test_the_order_is_the_same_every_time_it_is_asked():
    items = [make_item("c"), make_item("a"), make_item("b", difficulty=1)]
    first = query_bank(items, BankQuery(limit=3))
    second = query_bank(list(reversed(items)), BankQuery(limit=3))
    assert [item.id for item in first] == [item.id for item in second] == ["b", "a", "c"]


def test_a_limit_of_zero_asks_for_nothing():
    assert query_bank([make_item("a")], BankQuery(limit=0)) == []


def test_recently_seen_is_read_from_the_review_the_harness_already_wrote():
    states = [
        SpacedItemState(student_id="s1", item_id="yesterday", interval_days=1, due_date=TODAY),
        SpacedItemState(
            student_id="s1", item_id="three-weeks-ago", interval_days=21, due_date=TODAY
        ),
    ]
    assert last_seen(states[0]) == date(2026, 9, 13)
    assert seen_recently(states, TODAY, days=2) == frozenset({"yesterday"})
