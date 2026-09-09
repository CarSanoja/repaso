import pytest

from repaso.config.pricing import UnpricedModel
from repaso.tools.call_cost import CallCost, cache_saving_usd, cost_for, cost_or_none
from repaso.tools.model_usage import CallUsage

SONNET = "us.anthropic.claude-sonnet-4-6"
MICRO = "us.amazon.nova-micro-v1:0"


def test_each_token_class_is_charged_at_its_own_rate():
    usage = CallUsage(
        input_tokens=1000,
        output_tokens=1000,
        cache_read_tokens=1000,
        cache_write_tokens=1000,
    )
    cost = cost_for(SONNET, usage)

    assert cost.input_usd == pytest.approx(0.003)
    assert cost.output_usd == pytest.approx(0.015)
    assert cost.cache_read_usd == pytest.approx(0.0003)
    assert cost.cache_write_usd == pytest.approx(0.00375)
    assert cost.total_usd == pytest.approx(0.003 + 0.015 + 0.0003 + 0.00375)


def test_reasoning_tokens_are_charged_as_output():
    reasoned = cost_for(SONNET, CallUsage(reasoning_tokens=2000))
    written = cost_for(SONNET, CallUsage(output_tokens=2000))

    assert reasoned.reasoning_usd == pytest.approx(written.output_usd)
    assert reasoned.output_usd == 0.0


def test_the_measured_cache_pair_prices_the_way_the_provider_reports_it():
    cold = cost_for(SONNET, CallUsage(input_tokens=15, output_tokens=4, cache_write_tokens=3723))
    warm = cost_for(SONNET, CallUsage(input_tokens=15, output_tokens=4, cache_read_tokens=3723))

    assert cold.total_usd > warm.total_usd
    assert warm.cache_read_usd == pytest.approx(3723 * 0.0003 / 1000)


def test_a_cache_hit_is_worth_what_the_same_tokens_would_have_cost_uncached():
    usage = CallUsage(cache_read_tokens=3723)
    saved = cache_saving_usd(SONNET, usage)

    assert saved == pytest.approx(3723 * (0.003 - 0.0003) / 1000)
    assert cache_saving_usd(SONNET, CallUsage()) == 0.0


def test_a_model_whose_cache_write_is_free_charges_nothing_to_write():
    cost = cost_for(MICRO, CallUsage(cache_write_tokens=10_000))
    assert cost.cache_write_usd == 0.0


def test_costs_add_across_calls():
    total = CallCost(input_usd=0.1, cache_read_usd=0.01) + CallCost(
        output_usd=0.2, reasoning_usd=0.05
    )
    assert total.total_usd == pytest.approx(0.36)


def test_an_unpriced_model_raises_rather_than_costing_nothing():
    with pytest.raises(UnpricedModel, match="mistral"):
        cost_for("us.mistral.large", CallUsage(input_tokens=10))
    assert cost_or_none("us.mistral.large", CallUsage(input_tokens=10)) is None


def test_a_call_with_no_usage_costs_nothing():
    assert cost_for(SONNET, CallUsage()).total_usd == 0.0
