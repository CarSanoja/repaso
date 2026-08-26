import pytest

from repaso.config.models import ModelRole
from repaso.schemas.item import Item, ItemKind
from repaso.schemas.review import QuarantineKind
from repaso.simulator import cohort, demo_clock
from repaso.simulator.archetypes import Archetype
from repaso.simulator.demo_clock import (
    OPEN_GRADE,
    DemoClockResult,
    StalePrimeError,
    _assert_primes_drained,
    _settle_open_prime,
    build_offline_services,
    run_demo_clock,
)
from repaso.simulator.stub_model import AutoStubModel
from repaso.simulator.student_sim import INJECTION_REPLY, SimulatedAnswer

SEED = 20260910
HEDGED_TEXT = "creo que si porque los dos se parecen"
SCRIPTED_MIX = [(Archetype.INJECTOR, 1), (Archetype.AMBIGUOUS, 2)]


def _scripted_answer(
    seed: int, student_id: str, archetype: Archetype, day: int, item: Item
) -> SimulatedAnswer:
    if item.kind is not ItemKind.OPEN:
        return SimulatedAnswer(
            text=item.answer_key, correct_intent=True, latency_seconds=30.0, responded=True
        )
    if archetype is Archetype.INJECTOR:
        return SimulatedAnswer(
            text=INJECTION_REPLY, correct_intent=False, latency_seconds=30.0, responded=True
        )
    return SimulatedAnswer(
        text=HEDGED_TEXT, correct_intent=True, latency_seconds=50.0, responded=True
    )


@pytest.fixture
def scripted_cohort(monkeypatch):
    monkeypatch.setattr(cohort, "COHORT_MIX", SCRIPTED_MIX)
    monkeypatch.setattr(demo_clock, "simulate_answer", _scripted_answer)


async def test_screened_injection_on_an_open_item_does_not_shift_later_grades(
    settings, scripted_cohort
):
    result = await run_demo_clock(settings, days=2, seed=SEED)

    assert result.dropped_open_primes >= 1
    assert result.planted_hedged >= 1
    assert (
        result.quarantines_by_kind[QuarantineKind.LOW_CONFIDENCE_GRADE.value]
        == result.planted_hedged
    )


async def test_the_injector_still_quarantines_while_its_prime_is_dropped(
    settings, scripted_cohort
):
    result = await run_demo_clock(settings, days=2, seed=SEED)

    assert result.planted_injections >= 1
    assert (
        result.quarantines_by_kind[QuarantineKind.INJECTION_ATTEMPT.value]
        == result.planted_injections
    )


async def test_the_judge_queue_is_empty_after_every_simulated_day(settings, scripted_cohort):
    result = await run_demo_clock(settings, days=3, seed=SEED)
    services = build_offline_services(settings)

    assert result.days == 3
    assert services.models[ModelRole.JUDGE].pending(OPEN_GRADE) == 0


def test_a_stale_prime_is_dropped_and_never_counted_as_a_planted_hedge(settings):
    services = build_offline_services(settings)
    result = DemoClockResult(days=1, students=1)
    demo_clock._prime_open_grade(services, correct=True, hedged=True)

    _settle_open_prime(services, result, hedged=True)

    assert result.dropped_open_primes == 1
    assert result.planted_hedged == 0
    assert services.models[ModelRole.JUDGE].pending(OPEN_GRADE) == 0


def test_a_consumed_prime_counts_as_a_planted_hedge(settings):
    services = build_offline_services(settings)
    result = DemoClockResult(days=1, students=1)

    _settle_open_prime(services, result, hedged=True)

    assert result.dropped_open_primes == 0
    assert result.planted_hedged == 1


def test_a_leaked_prime_fails_the_day_end_tripwire(settings):
    services = build_offline_services(settings)
    demo_clock._prime_open_grade(services, correct=True, hedged=False)

    with pytest.raises(StalePrimeError, match="never reached the judge"):
        _assert_primes_drained(services)


def test_pending_and_drop_pending_report_the_queue_honestly():
    model = AutoStubModel()

    assert model.pending(OPEN_GRADE) == 0
    model.prime(OPEN_GRADE, {"confidence": 0.3})
    model.prime(OPEN_GRADE, {"confidence": 0.92})
    assert model.pending(OPEN_GRADE) == 2
    assert model.drop_pending(OPEN_GRADE) == 2
    assert model.pending(OPEN_GRADE) == 0
    assert model.drop_pending(OPEN_GRADE) == 0
