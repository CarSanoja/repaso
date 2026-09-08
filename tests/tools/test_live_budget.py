import pytest

from repaso.config.models import ModelRole, model_for
from tests.live.budget import (
    CONSERVATIVE_INPUT_TOKENS,
    CONSERVATIVE_OUTPUT_TOKENS,
    LiveBudgetExceeded,
    enforce_budget,
    estimate_budget,
)
from tests.live.environment import (
    DEFAULT_BUDGET_USD,
    DEFAULT_SAMPLES,
    DISABLED_REASON,
    NO_REGION_REASON,
    LiveEnvironmentInvalid,
    read_environment,
    skip_reason,
)
from tests.live.registry import build_registry
from tests.live.routing import routing_model_ids

ROUTING_MODELS = routing_model_ids()


def enabled_env(**overrides) -> dict[str, str]:
    return {"REPASO_LIVE_TESTS": "1", "AWS_REGION": "us-east-1", **overrides}


def test_absent_environment_reads_as_disabled_with_documented_defaults():
    environment = read_environment({})
    assert environment.enabled is False
    assert environment.region is None
    assert environment.samples == DEFAULT_SAMPLES
    assert environment.budget_usd == DEFAULT_BUDGET_USD
    assert skip_reason(environment) == DISABLED_REASON


def test_the_flag_alone_is_not_enough_without_a_region():
    environment = read_environment({"REPASO_LIVE_TESTS": "1"})
    assert environment.enabled is True
    assert skip_reason(environment) == NO_REGION_REASON


def test_repaso_region_wins_over_the_ambient_aws_region():
    environment = read_environment(
        enabled_env(REPASO_AWS_REGION="us-west-2", AWS_REGION="eu-west-1")
    )
    assert environment.region == "us-west-2"
    assert skip_reason(environment) is None


def test_blank_region_values_do_not_count_as_configuration():
    environment = read_environment({"REPASO_LIVE_TESTS": "1", "REPASO_AWS_REGION": "  "})
    assert environment.region is None


def test_anything_but_one_leaves_the_tier_disabled():
    for value in ("0", "true", "yes", ""):
        assert read_environment({"REPASO_LIVE_TESTS": value}).enabled is False


def test_samples_and_budget_are_read_from_the_environment():
    environment = read_environment(
        enabled_env(REPASO_LIVE_SAMPLES="12", REPASO_LIVE_BUDGET_USD="0.75")
    )
    assert environment.samples == 12
    assert environment.budget_usd == 0.75


def test_unparsable_sample_count_names_the_variable():
    with pytest.raises(LiveEnvironmentInvalid, match="REPASO_LIVE_SAMPLES"):
        read_environment(enabled_env(REPASO_LIVE_SAMPLES="many"))


def test_a_run_of_zero_samples_is_refused():
    with pytest.raises(LiveEnvironmentInvalid, match="at least 1"):
        read_environment(enabled_env(REPASO_LIVE_SAMPLES="0"))


def test_a_budget_of_zero_is_refused():
    with pytest.raises(LiveEnvironmentInvalid, match="above zero"):
        read_environment(enabled_env(REPASO_LIVE_BUDGET_USD="0"))


def test_estimate_counts_every_sample_of_every_schema_plus_the_routing_pings():
    probes = build_registry()
    estimate = estimate_budget(probes, ROUTING_MODELS, samples=5, limit_usd=DEFAULT_BUDGET_USD)
    assert estimate.conformance_calls == len(probes) * 5
    assert estimate.routing_calls == len(ROUTING_MODELS)
    assert estimate.calls == len(probes) * 5 + len(ROUTING_MODELS)


def test_estimate_grows_with_the_sample_count():
    probes = build_registry()
    one = estimate_budget(probes, (), samples=1, limit_usd=10.0)
    ten = estimate_budget(probes, (), samples=10, limit_usd=10.0)
    assert ten.estimated_usd == pytest.approx(one.estimated_usd * 10)


def test_the_allowance_charged_per_call_is_the_conservative_one():
    probe = next(p for p in build_registry() if p.role is ModelRole.PROBE)
    estimate = estimate_budget([probe], (), samples=1, limit_usd=10.0)
    price = CONSERVATIVE_INPUT_TOKENS * 0.000035 + CONSERVATIVE_OUTPUT_TOKENS * 0.00014
    assert model_for(probe.role) == "us.amazon.nova-micro-v1:0"
    assert estimate.estimated_usd == pytest.approx(price / 1000)


def test_the_default_sample_count_fits_inside_the_default_budget():
    estimate = estimate_budget(
        build_registry(), ROUTING_MODELS, DEFAULT_SAMPLES, DEFAULT_BUDGET_USD
    )
    assert estimate.within_budget
    assert round(estimate.estimated_usd, 2) == 0.66


def test_the_documented_ceiling_falls_between_fifteen_and_sixteen_samples():
    probes = build_registry()
    fits = estimate_budget(probes, ROUTING_MODELS, 15, DEFAULT_BUDGET_USD)
    over = estimate_budget(probes, ROUTING_MODELS, 16, DEFAULT_BUDGET_USD)
    assert fits.within_budget
    assert not over.within_budget


def test_an_affordable_run_is_announced_and_allowed():
    said: list[str] = []
    estimate = estimate_budget(build_registry(), ROUTING_MODELS, 5, DEFAULT_BUDGET_USD)
    assert enforce_budget(estimate, said.append) is estimate
    assert "within" in said[0]
    assert "$" in said[0]


def test_an_unaffordable_run_is_announced_and_refused():
    said: list[str] = []
    estimate = estimate_budget(build_registry(), ROUTING_MODELS, 5000, limit_usd=0.01)
    with pytest.raises(LiveBudgetExceeded, match="OVER"):
        enforce_budget(estimate, said.append)
    assert said and "OVER" in said[0]
