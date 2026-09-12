import time

from repaso.core.bank.query import BankQuery, query_bank
from repaso.core.bank.sources import bank_items
from repaso.schemas.item import BloomLevel, ItemStatus
from tests.bank.items import make_item
from tests.orchestration.fixtures import make_services, seed_family

ITEM_COUNT = 200
QUERY_BUDGET_SECONDS = 0.05


def test_the_bank_is_what_this_family_owns_plus_what_is_shared(settings):
    services = make_services(settings)
    family, _ = seed_family(services.store)
    other, _ = seed_family(services.store, family_id="f2", chat_ref="200")
    services.store.put_item(make_item("mine", family_id=family.id))
    services.store.put_item(make_item("theirs", family_id=other.id))
    services.store.put_item(make_item("shared", family_id=None))

    found = {item.id for item in bank_items(services, family, 4)}

    assert "mine" in found
    assert "shared" in found
    assert "theirs" not in found


def test_a_rejected_item_never_enters_the_bank(settings):
    services = make_services(settings)
    family, _ = seed_family(services.store)
    services.store.put_item(make_item("bad", family_id=family.id, status=ItemStatus.REJECTED))

    assert bank_items(services, family, 4) == []


def test_the_query_answers_from_the_store_without_a_model(settings):
    services = make_services(settings)
    family, _ = seed_family(services.store)
    for index in range(ITEM_COUNT):
        services.store.put_item(
            make_item(
                f"i{index:03d}",
                family_id=family.id,
                stem=f"pregunta {index}",
                bloom=BloomLevel.APPLY if index % 2 else BloomLevel.REMEMBER,
            )
        )

    started = time.perf_counter()
    items = bank_items(services, family, 4)
    found = query_bank(items, BankQuery(bloom=BloomLevel.APPLY, limit=3))
    elapsed = time.perf_counter() - started

    assert len(found) == 3
    assert all(item.bloom is BloomLevel.APPLY for item in found)
    assert elapsed < QUERY_BUDGET_SECONDS
    assert all(model.calls == [] for model in services.models.values())
