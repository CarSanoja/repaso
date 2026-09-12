from repaso.schemas.family import Family
from repaso.schemas.item import Item, ItemStatus
from repaso.schemas.provenance import Source

SUBJECT = "math"
SHARED_SOURCES = frozenset({Source.SYSTEM, Source.SIMULATED})


def _shared(services, item: Item) -> bool:
    if item.family_id is not None or item.variant_of is not None:
        return False
    return services.settings.local_mode or item.provenance.source in SHARED_SOURCES


def bank_items(services, family: Family, grade: int, subject: str = SUBJECT) -> list[Item]:
    competencies = {c.id for c in services.retriever.list_competencies(grade, subject)}
    items = {
        item.id: item
        for item in services.store.list_family_items(family.id)
        if item.competency_id in competencies
        and item.status is ItemStatus.ACTIVE
        and item.variant_of is None
    }
    for competency_id in competencies:
        for item in services.store.list_items_by_competency(competency_id, ItemStatus.ACTIVE):
            if _shared(services, item):
                items[item.id] = item
    return list(items.values())
