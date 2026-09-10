from repaso.simulator.demo_cost import NO_RATE, NO_USAGE, cost_line
from repaso.tools.cassette import CassetteEntry
from repaso.tools.cassette_cost import cassette_spend
from repaso.tools.model_usage import CallUsage

PAYLOAD = {"safe": True, "reasons": []}
SONNET = "us.anthropic.claude-sonnet-4-6"


def entry(usage: CallUsage | None, model_id: str | None = SONNET) -> CassetteEntry:
    return CassetteEntry(
        role="classify",
        kind="structured_output",
        output_model="IntakeDecision",
        payload=PAYLOAD,
        model_id=model_id,
        usage=usage,
    )


def line(entries: list[CassetteEntry]) -> str:
    return cost_line(cassette_spend(entries))


def test_the_line_reports_the_tokens_and_the_dollars_the_recording_measured():
    printed = line([entry(CallUsage(input_tokens=1200, output_tokens=340))])

    assert "1,200 input + 340 output tokens" in printed
    assert "$0.0087" in printed
    assert "1 recorded model calls" in printed


def test_a_cassette_with_no_usage_says_so_instead_of_printing_zero():
    printed = line([entry(None), entry(None)])

    assert printed == f"cost: {NO_USAGE} reported by any of the 2 recorded model calls"


def test_an_empty_cassette_reads_as_nothing_reported():
    assert NO_USAGE in line([])


def test_a_partly_measured_cassette_says_how_much_is_missing():
    printed = line([entry(CallUsage(input_tokens=1200, output_tokens=340)), entry(None)])

    assert f"1 with {NO_USAGE} reported" in printed


def test_an_entry_the_price_table_does_not_cover_is_named_apart():
    printed = line(
        [entry(CallUsage(input_tokens=100, output_tokens=10), model_id="some.other.model")]
    )

    assert f"1 with {NO_RATE} in the price table" in printed
    assert "$0.0000" in printed


def test_a_fully_measured_cassette_does_not_mention_a_gap():
    printed = line([entry(CallUsage(input_tokens=10, output_tokens=5))])

    assert NO_USAGE not in printed
    assert NO_RATE not in printed
