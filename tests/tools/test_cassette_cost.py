import pytest

from repaso.tools.cassette import CassetteEntry
from repaso.tools.cassette_cost import cassette_spend, model_ids_in
from repaso.tools.model_usage import CallUsage

SONNET = "us.anthropic.claude-sonnet-4-6"
NOVA = "us.amazon.nova-micro-v1:0"
PAYLOAD = {"safe": True, "reasons": []}


def entry(
    usage: CallUsage | None = None, model_id: str | None = SONNET, role: str = "classify"
) -> CassetteEntry:
    return CassetteEntry(
        role=role,
        kind="structured_output",
        output_model="IntakeDecision",
        payload=PAYLOAD,
        model_id=model_id,
        usage=usage,
    )


def test_the_dollars_are_the_rate_of_the_model_each_entry_names():
    entries = [
        entry(CallUsage(input_tokens=1000, output_tokens=100)),
        entry(CallUsage(input_tokens=1000, output_tokens=100), model_id=NOVA),
    ]

    spend = cassette_spend(entries)

    assert spend.usage.input_tokens == 2000
    assert spend.usage.output_tokens == 200
    assert spend.usd == pytest.approx(0.003 + 0.0015 + 0.000035 + 0.000014)
    assert (spend.calls, spend.reported, spend.priced) == (2, 2, 2)


def test_an_entry_without_usage_is_counted_apart_from_one_that_reported_zero():
    spend = cassette_spend([entry(), entry(CallUsage())])

    assert (spend.calls, spend.reported, spend.priced) == (2, 1, 1)
    assert spend.unreported == 1
    assert spend.usd == 0.0


def test_an_entry_whose_model_has_no_rate_keeps_its_tokens_and_earns_no_dollars():
    spend = cassette_spend(
        [entry(CallUsage(input_tokens=800, output_tokens=80), model_id="some.other.model")]
    )

    assert spend.usage.input_tokens == 800
    assert spend.priced == 0
    assert spend.unpriced == 1
    assert spend.usd == 0.0


def test_an_entry_that_names_no_model_cannot_be_priced():
    spend = cassette_spend([entry(CallUsage(input_tokens=800), model_id=None)])

    assert (spend.reported, spend.priced) == (1, 0)
    assert spend.usd == 0.0


def test_an_empty_cassette_spends_nothing():
    spend = cassette_spend([])

    assert (spend.calls, spend.reported, spend.priced) == (0, 0, 0)
    assert spend.usd == 0.0


def test_the_model_ids_are_listed_once_each():
    entries = [entry(), entry(model_id=NOVA), entry(), entry(model_id=None)]

    assert model_ids_in(entries) == [NOVA, SONNET]
