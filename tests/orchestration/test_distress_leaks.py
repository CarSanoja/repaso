import json

from repaso.core.orchestration.distress import RECORD_PREFIX
from repaso.core.orchestration.privacy import forget_family
from repaso.core.orchestration.study_channel import handle_study_text
from repaso.core.telemetry.sink import LocalTelemetrySink
from repaso.schemas.turn import TurnIntent
from repaso.tools.episode_log import list_attempts
from repaso.tools.grade_words import WORDS_FILENAME
from tests.orchestration.fixtures import seed_family
from tests.orchestration.test_study_help import open_with, reads
from tests.orchestration.test_turn_router import (
    READ_ROLE,
    says,
    seed_item,
    seed_session,
    services_with_recorder,
)
from tests.orchestration.test_turn_router import (
    reads as reads_chat,
)

WROTE = "un senor grande me toco y me dijo que no dijera nada"


async def said_it(settings):
    services = services_with_recorder(settings)
    services.telemetry = LocalTelemetrySink(
        settings.local_data_dir / "telemetry.jsonl", services.clock
    )
    family, student = seed_family(services.store)
    seed_item(services.store, "i1")
    seed_session(services, student.id, ["i1"])
    reads_chat(services, TurnIntent.DISTRESS)
    await says(services, family, WROTE)
    return services, family, student


async def test_forget_takes_the_row_that_says_it_happened(settings):
    services, family, _ = await said_it(settings)
    assert services.store.list_records(family.id, RECORD_PREFIX)

    forget_family(services, family)

    assert services.store.list_records(family.id, RECORD_PREFIX) == []


async def test_the_words_never_become_an_attempt_anyone_can_be_shown(settings):
    services, family, student = await said_it(settings)

    assert list_attempts(services.store, family.id, student.id) == []
    assert services.store.list_records(family.id, "answer#") == []
    assert services.store.list_records(family.id, "episode#") == []


async def test_no_stored_word_row_is_written_for_what_was_said(settings):
    services, _, student = await said_it(settings)

    words = services.settings.local_data_dir / "state" / WORDS_FILENAME
    assert not words.exists() or WROTE not in words.read_text(encoding="utf-8")
    assert services.grade_log.by_student(student.id) == []


async def test_the_next_turn_is_read_with_none_of_those_words(settings):
    services, family, _ = await said_it(settings)
    reads_chat(services, TurnIntent.ANOTHER_QUESTION)

    await says(services, family, "otra pregunta porfa")

    reader = services.models[READ_ROLE]
    assert WROTE not in reader.systems[-1]
    assert WROTE not in reader.prompts[-1]


async def test_nothing_written_anywhere_for_this_family_repeats_the_words(settings):
    services, family, student = await said_it(settings)

    everything = [r.model_dump(mode="json") for r in services.store.list_records(family.id)]
    everything += [event.model_dump(mode="json") for event in services.telemetry.events]
    written = json.dumps(everything, ensure_ascii=False)
    assert WROTE not in written
    assert student.id in written


async def test_a_sitting_leaves_no_trace_of_the_words_either(settings):
    services, family, student, _ = open_with(settings)
    reads(services, TurnIntent.DISTRESS)

    await handle_study_text(services, family, WROTE, 5.0, "m1")

    kept = [record.model_dump(mode="json") for record in services.store.list_records(family.id)]
    assert WROTE not in json.dumps(kept, ensure_ascii=False)
    assert list_attempts(services.store, family.id, student.id) == []
