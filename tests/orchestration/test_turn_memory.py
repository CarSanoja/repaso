import asyncio

from repaso.core.orchestration.turn_memory import (
    MAX_NOTES,
    SAID_LIMIT,
    close_window,
    history_lines,
    note,
    note_key,
    read_window,
    remember,
    tried_approaches,
)
from repaso.schemas.turn import TurnIntent
from tests.orchestration.fixtures import START, make_services, seed_family, seed_open_item

SESSION = "sess-1"


def answered(services, item, turn_id: str, said: str, correct: bool):
    return note(
        turn_id=turn_id,
        intent=TurnIntent.ANSWER,
        at=services.clock.now(),
        item=item,
        said=said,
        correct=correct,
    )


def test_a_fresh_session_remembers_nothing(settings):
    services = make_services(settings)

    window = read_window(services, "f1", SESSION)

    assert window.session_id == SESSION
    assert window.notes == []


def test_the_window_holds_the_question_the_answer_and_the_verdict(settings):
    services = make_services(settings)
    family, _ = seed_family(services.store)
    item = seed_open_item(services.store)

    remember(services, family.id, SESSION, answered(services, item, "m1", "la mitad", False))
    window = read_window(services, family.id, SESSION)

    assert [entry.turn_id for entry in window.notes] == ["m1"]
    line = history_lines(services, window)[0]
    assert "turn 1" in line
    assert "intent: answer" in line
    assert item.stem[:20] in line
    assert 'wrote: "la mitad"' in line
    assert "harness graded: incorrect" in line


def test_an_explanation_is_remembered_by_the_way_it_was_explained(settings):
    services = make_services(settings)
    family, _ = seed_family(services.store)
    item = seed_open_item(services.store)

    remember(
        services,
        family.id,
        SESSION,
        note(
            turn_id="m2",
            intent=TurnIntent.EXPLANATION,
            at=services.clock.now(),
            item=item,
            said="no entiendo",
            explained="bar split into parts",
        ),
    )
    window = read_window(services, family.id, SESSION)

    assert tried_approaches(window) == ["bar split into parts"]
    assert "explained with: bar split into parts" in history_lines(services, window)[0]


def test_the_same_turn_arriving_twice_is_remembered_once_and_in_place(settings):
    services = make_services(settings)
    family, _ = seed_family(services.store)
    item = seed_open_item(services.store)

    remember(services, family.id, SESSION, answered(services, item, "m1", "la mitad", False))
    remember(services, family.id, SESSION, answered(services, item, "m2", "2/4", True))
    remember(services, family.id, SESSION, answered(services, item, "m1", "la mitad", False))
    window = read_window(services, family.id, SESSION)

    assert [entry.turn_id for entry in window.notes] == ["m1", "m2"]


async def test_turns_written_at_the_same_time_all_survive(settings):
    services = make_services(settings)
    family, _ = seed_family(services.store)
    item = seed_open_item(services.store)

    async def write(turn_id: str):
        await asyncio.to_thread(
            remember, services, family.id, SESSION, answered(services, item, turn_id, "1/2", True)
        )

    await asyncio.gather(*(write(f"m{index}") for index in range(4)))
    window = read_window(services, family.id, SESSION)

    assert {entry.turn_id for entry in window.notes} == {"m0", "m1", "m2", "m3"}


def test_the_window_cannot_grow_past_its_cap(settings):
    services = make_services(settings)
    family, _ = seed_family(services.store)
    item = seed_open_item(services.store)

    for index in range(MAX_NOTES + 3):
        remember(services, family.id, SESSION, answered(services, item, f"m{index}", "1/2", True))
        services.clock.advance(minutes=1)
    window = read_window(services, family.id, SESSION)

    assert len(window.notes) == MAX_NOTES
    assert window.notes[-1].turn_id == f"m{MAX_NOTES + 2}"


def test_a_long_message_is_trimmed_before_it_is_stored(settings):
    services = make_services(settings)
    family, _ = seed_family(services.store)
    item = seed_open_item(services.store)

    remember(services, family.id, SESSION, answered(services, item, "m1", "x" * 400, False))
    window = read_window(services, family.id, SESSION)

    assert len(window.notes[0].said) == SAID_LIMIT


def test_closing_the_session_leaves_none_of_the_child_words_behind(settings):
    services = make_services(settings)
    family, _ = seed_family(services.store)
    item = seed_open_item(services.store)
    remember(services, family.id, SESSION, answered(services, item, "m1", "la mitad", False))

    close_window(services, family.id, SESSION)

    record = services.store.get_record(family.id, note_key(SESSION, "m1"))
    assert "la mitad" not in str(record.payload)
    kept = read_window(services, family.id, SESSION).notes[0]
    assert kept.said == ""
    assert (kept.item_id, kept.correct) == (item.id, False)


def test_the_window_carries_an_expiry_stamp(settings):
    services = make_services(settings)
    family, _ = seed_family(services.store)
    item = seed_open_item(services.store)

    remember(services, family.id, SESSION, answered(services, item, "m1", "1/2", True))
    record = services.store.get_record(family.id, note_key(SESSION, "m1"))

    assert record.payload["expires_at"] > int(START.timestamp())


def test_forgetting_the_family_takes_the_window_with_it(settings):
    services = make_services(settings)
    family, _ = seed_family(services.store)
    item = seed_open_item(services.store)
    remember(services, family.id, SESSION, answered(services, item, "m1", "la mitad", False))

    services.store.forget_family(family.id)

    assert services.store.get_record(family.id, note_key(SESSION, "m1")) is None
