from datetime import UTC, datetime

from repaso.schemas.item import Item, ItemKind
from repaso.schemas.provenance import Provenance, Source
from repaso.simulator.archetypes import PROFILES, Archetype
from repaso.simulator.student_sim import INJECTION_REPLY, ability_on_day, simulate_answer

SEED = 20260901


def make_item(item_id: str = "i1", kind: ItemKind = ItemKind.MCQ) -> Item:
    return Item(
        id=item_id,
        competency_id="math.g4.fractions.equivalence",
        kind=kind,
        difficulty=2,
        stem="Which fraction equals 2/4?",
        options=["1/2", "2/8", "3/4"] if kind is ItemKind.MCQ else [],
        answer_key="1/2",
        rationale="halves",
        rubric="2 points" if kind is ItemKind.OPEN else None,
        provenance=Provenance(source=Source.SIMULATED, created_at=datetime(2026, 9, 1, tzinfo=UTC)),
    )


def test_same_seed_reproduces_the_same_transcript():
    def transcript() -> list:
        return [
            simulate_answer(SEED, "s1", Archetype.STEADY_MASTERY, day, make_item())
            for day in range(14)
        ]

    assert transcript() == transcript()


def test_different_students_diverge():
    a = [simulate_answer(SEED, "s1", Archetype.STEADY_MASTERY, d, make_item()) for d in range(14)]
    b = [simulate_answer(SEED, "s2", Archetype.STEADY_MASTERY, d, make_item()) for d in range(14)]
    assert a != b


def test_steady_mastery_improves_over_time():
    early = ability_on_day(PROFILES[Archetype.STEADY_MASTERY], 0)
    late = ability_on_day(PROFILES[Archetype.STEADY_MASTERY], 13)
    assert late > early


def test_struggling_students_mostly_fail():
    answers = [
        simulate_answer(SEED, f"s{n}", Archetype.STRUGGLING, day, make_item())
        for n in range(5)
        for day in range(14)
    ]
    responded = [a for a in answers if a.responded]
    accuracy = sum(a.correct_intent for a in responded) / len(responded)
    assert accuracy < 0.5


def test_disengaged_students_stop_answering_after_dropout_day():
    late = [
        simulate_answer(SEED, "s1", Archetype.DISENGAGED, day, make_item())
        for day in range(6, 14)
    ]
    assert all(not answer.responded for answer in late)


def test_fast_guesser_answers_fast():
    answers = [
        simulate_answer(SEED, f"s{n}", Archetype.FAST_GUESSER, 3, make_item(f"i{n}"))
        for n in range(10)
    ]
    responded = [a for a in answers if a.responded]
    assert all(answer.latency_seconds < 10 for answer in responded)


def test_injector_plants_the_injection_on_day_two():
    answer = simulate_answer(SEED, "s1", Archetype.INJECTOR, 2, make_item())
    assert answer.text == INJECTION_REPLY


def test_wrong_mcq_answers_pick_a_distractor():
    answers = [
        simulate_answer(SEED, f"s{n}", Archetype.STRUGGLING, 0, make_item())
        for n in range(20)
    ]
    wrong = [a for a in answers if a.responded and not a.correct_intent]
    assert wrong
    assert all(a.text in {"2/8", "3/4"} for a in wrong)
