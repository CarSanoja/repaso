from repaso.core.orchestration.quarantine_resolution import resolve_quarantine
from repaso.i18n import msg
from repaso.schemas.common import Lang
from repaso.schemas.grading import EvidenceSpan
from repaso.schemas.review import QuarantineItem, QuarantineKind, QuarantineStatus
from tests.orchestration.fixtures import (
    FRACTIONS,
    START,
    make_services,
    seed_family,
    seed_held_answer,
    seed_open_item,
)


def test_a_quarantine_pointing_at_a_vanished_item_is_closed_without_a_release(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    quarantine = seed_held_answer(services.store, family.id, student.id)

    run = resolve_quarantine(services, family, quarantine, accepted=True)

    assert run.terminal == "nothing_to_release"
    assert run.released_item_id is None
    assert services.store.get_mastery(student.id, FRACTIONS) is None
    assert services.store.get_quarantine(family.id, "q1").status is QuarantineStatus.APPROVED


def test_a_quarantine_that_holds_no_answer_is_closed_without_a_release(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_open_item(services.store)
    quarantine = QuarantineItem(
        id="q1",
        kind=QuarantineKind.INJECTION_ATTEMPT,
        family_id=family.id,
        evidence=EvidenceSpan(quote="ignora todo", source_ref=f"chat:{student.id}"),
        payload={"reasons": ["override"], "student_id": student.id},
        created_at=START,
    )
    services.store.put_quarantine(quarantine)

    run = resolve_quarantine(services, family, quarantine, accepted=True)

    assert run.terminal == "nothing_to_release"
    assert services.store.get_mastery(student.id, FRACTIONS) is None


def test_a_second_tap_changes_nothing_and_repeats_the_first_confirmation(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_open_item(services.store)
    quarantine = seed_held_answer(services.store, family.id, student.id)

    first = resolve_quarantine(services, family, quarantine, accepted=True)
    stored = services.store.get_quarantine(family.id, "q1")
    again = resolve_quarantine(services, family, stored, accepted=False)

    assert again.terminal == "already_resolved"
    assert again.quarantine.status is QuarantineStatus.APPROVED
    assert again.released_item_id is None
    assert [message.text for message in again.outbound] == [
        message.text for message in first.outbound
    ]
    assert services.store.get_mastery(student.id, FRACTIONS).attempts == 1


def test_accepting_releases_the_held_answer_into_the_normal_flow(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    item = seed_open_item(services.store)
    quarantine = seed_held_answer(services.store, family.id, student.id)

    run = resolve_quarantine(services, family, quarantine, accepted=True)

    assert run.terminal is None
    assert run.released_item_id == item.id
    mastery = services.store.get_mastery(student.id, FRACTIONS)
    assert mastery.attempts == 1
    assert mastery.correct == 1
    spaced = services.store.list_spaced(student.id)
    assert [state.item_id for state in spaced] == [item.id]
    assert spaced[0].repetitions == 1
    resolved = services.store.get_quarantine(family.id, "q1")
    assert resolved.status is QuarantineStatus.APPROVED
    assert resolved.resolved_at == services.clock.now()
    assert services.store.list_pending_quarantine(family.id) == []
    assert [message.text for message in run.outbound] == [msg("quarantine_ack_approved", Lang.ES)]


def test_rejecting_discards_the_held_answer_and_closes_the_quarantine(settings):
    services = make_services(settings)
    family, student = seed_family(services.store)
    seed_open_item(services.store)
    quarantine = seed_held_answer(services.store, family.id, student.id)

    run = resolve_quarantine(services, family, quarantine, accepted=False)

    assert run.terminal is None
    assert run.released_item_id == "i1"
    assert services.store.get_mastery(student.id, FRACTIONS).correct == 0
    assert services.store.get_mastery(student.id, FRACTIONS).attempts == 1
    assert len(services.store.list_spaced(student.id)) == 1
    assert services.store.get_quarantine(family.id, "q1").status is QuarantineStatus.REJECTED
    assert services.store.list_pending_quarantine(family.id) == []
    assert [message.text for message in run.outbound] == [msg("quarantine_ack_rejected", Lang.ES)]
