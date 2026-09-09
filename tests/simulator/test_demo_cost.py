from repaso.simulator.demo_cost import NOT_RECORDED, cost_line, token_totals
from repaso.tools.cassette import CassetteEntry
from repaso.tools.model_usage import CallUsage

PAYLOAD = {"safe": True, "reasons": []}


def entry(usage: CallUsage | None) -> CassetteEntry:
    return CassetteEntry(
        role="classify",
        kind="structured_output",
        output_model="IntakeDecision",
        payload=PAYLOAD,
        usage=usage,
    )


def test_totals_add_up_over_the_entries_that_carry_usage():
    totals = token_totals([entry(CallUsage(input_tokens=100, output_tokens=20)), entry(None)])

    assert totals.calls == 2
    assert totals.priced == 1
    assert totals.unpriced == 1
    assert (totals.input_tokens, totals.output_tokens) == (100, 20)


def test_a_cassette_with_no_usage_reads_as_not_recorded():
    line = cost_line(token_totals([entry(None), entry(None)]))

    assert NOT_RECORDED in line
    assert "2" in line


def test_an_empty_cassette_reads_as_not_recorded():
    assert NOT_RECORDED in cost_line(token_totals([]))


def test_a_partly_priced_cassette_says_how_much_is_missing():
    priced = entry(CallUsage(input_tokens=1200, output_tokens=340))
    line = cost_line(token_totals([priced, entry(None)]))

    assert "1,200 input + 340 output" in line
    assert f"1 {NOT_RECORDED}" in line


def test_a_fully_priced_cassette_does_not_mention_a_gap():
    line = cost_line(token_totals([entry(CallUsage(input_tokens=10, output_tokens=5))]))

    assert NOT_RECORDED not in line
    assert "1 of 1 model calls" in line
