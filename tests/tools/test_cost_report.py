from datetime import UTC, datetime, timedelta

import pytest

from repaso.tools.call_cost import cost_or_none
from repaso.tools.call_ledger import CallOrigin, CallOutcome, CallRecord
from repaso.tools.cost_report import NOT_REPORTED, build_cost_report, percentile
from repaso.tools.cost_table import render_cost_report
from repaso.tools.model_usage import CallUsage

SONNET = "us.anthropic.claude-sonnet-4-6"
HAIKU = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
AT = datetime(2026, 9, 12, 9, 30, tzinfo=UTC)


def call(
    number: int,
    role: str = "judge",
    model_id: str = SONNET,
    usage: CallUsage | None = None,
    latency_ms: float = 100.0,
    origin: CallOrigin = CallOrigin.LIVE,
    outcome: CallOutcome = CallOutcome.OK,
    kind: str = "structured_output",
) -> CallRecord:
    return CallRecord(
        call_id=f"c{number}",
        at=AT + timedelta(seconds=number),
        role=role,
        model_id=model_id,
        kind=kind,
        output_model="OpenGrade" if kind == "structured_output" else None,
        origin=origin,
        outcome=outcome,
        latency_ms=latency_ms,
        usage=usage,
        cost=None if usage is None else cost_or_none(model_id, usage),
    )


def test_the_totals_are_the_sum_of_the_lines():
    records = [
        call(1, usage=CallUsage(input_tokens=1000, output_tokens=100)),
        call(2, role="probe", model_id=HAIKU, usage=CallUsage(input_tokens=500, output_tokens=50)),
    ]
    report = build_cost_report(records)

    assert report.calls == 2
    assert report.usage == CallUsage(input_tokens=1500, output_tokens=150)
    assert report.total_usd == pytest.approx(
        1000 * 0.003 / 1000 + 100 * 0.015 / 1000 + 500 * 0.001 / 1000 + 50 * 0.005 / 1000
    )
    assert sum(group.total_usd for group in report.by_role) == pytest.approx(report.total_usd)
    assert sum(group.total_usd for group in report.by_model) == pytest.approx(report.total_usd)
    assert sum(group.total_usd for group in report.by_kind) == pytest.approx(report.total_usd)


def test_spend_is_split_by_role_by_model_and_by_call_kind():
    records = [
        call(1, role="judge", usage=CallUsage(input_tokens=1000)),
        call(2, role="probe", model_id=HAIKU, usage=CallUsage(input_tokens=1000)),
        call(3, role="probe", model_id=HAIKU, kind="stream", usage=CallUsage(input_tokens=1000)),
    ]
    report = build_cost_report(records)

    assert [(g.name, g.calls) for g in report.by_role] == [("judge", 1), ("probe", 2)]
    assert [(g.name, g.calls) for g in report.by_model] == [(HAIKU, 2), (SONNET, 1)]
    assert [(g.name, g.calls) for g in report.by_kind] == [("stream", 1), ("structured_output", 2)]


def test_a_cache_hit_is_reported_as_what_it_saved():
    warm = call(1, usage=CallUsage(input_tokens=15, output_tokens=4, cache_read_tokens=3723))
    report = build_cost_report([warm])

    assert report.usage.cache_read_tokens == 3723
    assert report.cache_saving_usd == pytest.approx(3723 * (0.003 - 0.0003) / 1000)


def test_a_run_that_wrote_the_cache_saved_nothing_yet():
    cold = call(1, usage=CallUsage(input_tokens=15, output_tokens=4, cache_write_tokens=3723))
    report = build_cost_report([cold])

    assert report.cache_saving_usd == 0.0
    assert report.cost.cache_write_usd == pytest.approx(3723 * 0.00375 / 1000)


def test_latency_is_reported_per_role():
    records = [call(n, role="judge", latency_ms=float(n * 100)) for n in range(1, 5)]
    report = build_cost_report(records)

    assert [(row.name, row.calls) for row in report.latency] == [("judge", 4)]
    assert (report.latency[0].p50_ms, report.latency[0].p95_ms) == (200.0, 400.0)


def test_a_ledger_with_no_usage_says_so_rather_than_reporting_zero():
    report = build_cost_report([call(1), call(2)])

    assert (report.calls, report.reported, report.priced) == (2, 0, 0)
    assert report.total_usd == 0.0
    assert report.reasoning_share is None

    table = render_cost_report(report)
    assert f"spend: {NOT_REPORTED}" in table
    assert f"reasoning tokens: {NOT_REPORTED}" in table


def test_a_run_that_reports_no_reasoning_does_not_claim_a_zero_share():
    report = build_cost_report([call(1, usage=CallUsage(input_tokens=10, output_tokens=5))])
    assert report.reasoning_share is None


def test_a_reported_reasoning_count_becomes_a_share_of_what_was_generated():
    usage = CallUsage(input_tokens=10, output_tokens=60, reasoning_tokens=40)
    report = build_cost_report([call(1, usage=usage)])

    assert report.reasoning_share == pytest.approx(0.4)
    assert "reasoning tokens: 40 of 100 generated (40.0%)" in render_cost_report(report)


def test_a_replayed_run_is_never_presented_as_a_measurement():
    live = build_cost_report([call(1, usage=CallUsage(input_tokens=10))])
    replayed = build_cost_report(
        [call(1, usage=CallUsage(input_tokens=10), origin=CallOrigin.REPLAYED)]
    )

    assert live.measured is True
    assert replayed.measured is False
    assert "not a live measurement" in render_cost_report(replayed)
    assert "1 replayed" in render_cost_report(replayed)


def test_a_mixed_run_is_not_a_measurement_either():
    report = build_cost_report(
        [
            call(1, usage=CallUsage(input_tokens=10)),
            call(2, usage=CallUsage(input_tokens=10), origin=CallOrigin.REPLAYED),
        ]
    )
    assert report.measured is False


def test_outcomes_are_counted_and_named():
    report = build_cost_report(
        [
            call(1, usage=CallUsage(input_tokens=10)),
            call(2, outcome=CallOutcome.FAILED),
            call(3, outcome=CallOutcome.DENIED),
        ]
    )

    assert report.outcomes == {"denied": 1, "failed": 1, "ok": 1}
    assert "outcomes: 1 denied, 1 failed, 1 ok" in render_cost_report(report)


def test_a_call_no_rate_covers_is_counted_apart_from_one_that_reported_nothing():
    records = [
        call(1, model_id="us.mistral.large", usage=CallUsage(input_tokens=10)),
        call(2),
    ]
    report = build_cost_report(records)

    assert (report.calls, report.reported, report.priced) == (2, 1, 0)
    table = render_cost_report(report)
    assert "1 of 2 without reported usage" in table
    assert "1 priced by no rate in the table" in table


def test_an_empty_ledger_reports_nothing_and_divides_by_nothing():
    report = build_cost_report([])

    assert (report.calls, report.total_usd, report.latency) == (0, 0.0, [])
    assert report.measured is False
    assert render_cost_report(report) == "no model calls in this ledger"


def test_percentile_uses_nearest_rank():
    assert percentile([10.0, 20.0, 30.0, 40.0], 0.5) == 20.0
    assert percentile([10.0, 20.0, 30.0, 40.0], 0.95) == 40.0
    assert percentile([7.0], 0.95) == 7.0
