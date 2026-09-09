import pytest

from repaso.config.pricing import (
    PRICES,
    TokenPrice,
    UnpricedModel,
    configured_models,
    estimate_cost_usd,
    price_for,
)


def test_every_configured_model_carries_a_price():
    missing = sorted(configured_models() - set(PRICES))
    assert missing == []


def test_price_table_holds_nothing_the_fleet_does_not_use():
    stray = sorted(set(PRICES) - configured_models())
    assert stray == []


def test_output_tokens_are_never_cheaper_than_input_tokens():
    for model_id, price in PRICES.items():
        assert price.output_usd_per_1k >= price.input_usd_per_1k, model_id


def test_estimate_charges_input_and_output_at_their_own_rates():
    cost = estimate_cost_usd("us.amazon.nova-micro-v1:0", 2000, 1000)
    assert cost == pytest.approx(2 * 0.000035 + 1 * 0.00014)


def test_estimate_of_an_unused_call_is_zero():
    assert estimate_cost_usd("us.anthropic.claude-sonnet-4-6", 0, 0) == 0.0


def test_unknown_model_raises_instead_of_estimating_zero():
    with pytest.raises(UnpricedModel, match="mistral"):
        estimate_cost_usd("us.mistral.large", 100, 100)


def test_price_for_names_the_model_it_could_not_find():
    with pytest.raises(UnpricedModel, match="us.meta.llama"):
        price_for("us.meta.llama")


def test_negative_token_counts_are_rejected():
    with pytest.raises(ValueError, match="negative"):
        estimate_cost_usd("us.amazon.nova-lite-v1:0", -1, 0)


def test_prices_reject_unknown_fields_and_stay_frozen():
    price = TokenPrice(
        input_usd_per_1k=0.001,
        output_usd_per_1k=0.005,
        cache_read_usd_per_1k=0.0001,
        cache_write_usd_per_1k=0.00125,
    )
    with pytest.raises(ValueError):
        TokenPrice(
            input_usd_per_1k=0.001,
            output_usd_per_1k=0.005,
            cache_read_usd_per_1k=0.0001,
            cache_write_usd_per_1k=0.00125,
            currency="USD",
        )
    with pytest.raises(ValueError):
        price.input_usd_per_1k = 0.002


def test_a_cache_read_is_cheaper_than_the_input_it_replaces():
    for model_id, price in PRICES.items():
        assert price.cache_read_usd_per_1k < price.input_usd_per_1k, model_id


def test_a_cache_write_is_never_cheaper_than_the_input_it_stores():
    for model_id, price in PRICES.items():
        assert price.cache_write_usd_per_1k >= 0.0, model_id
        if price.cache_write_usd_per_1k:
            assert price.cache_write_usd_per_1k > price.input_usd_per_1k, model_id


def test_reasoning_is_charged_at_the_output_rate():
    for price in PRICES.values():
        assert price.reasoning_usd_per_1k == price.output_usd_per_1k


def test_every_configured_model_carries_all_four_rates():
    assert set(PRICES) == configured_models()
    for model_id, price in PRICES.items():
        recorded = price.model_dump()
        assert set(recorded) == {
            "input_usd_per_1k",
            "output_usd_per_1k",
            "cache_read_usd_per_1k",
            "cache_write_usd_per_1k",
        }, model_id
