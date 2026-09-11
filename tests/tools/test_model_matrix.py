from datetime import UTC, datetime

import pytest

from repaso.config.pricing import configured_models
from tests.live.calls import CallOutcome
from tests.live.matrix import build_matrix
from tests.live.registry import build_registry
from tests.live.sweep import (
    MAX_THROTTLE_ATTEMPTS,
    THROTTLE_MARK,
    SweepRow,
    build_cases,
    run_case,
    run_sweep,
)
from tests.live.table import render_matrix
from tests.tools.live_fixtures import PAYLOADS, RampClock

MEASURED_AT = datetime(2026, 9, 12, 7, 0, tzinfo=UTC)
MODELS = ("model-a", "model-b")


class ThrottlingModel:
    def __init__(self, refusals: int) -> None:
        self._refusals = refusals
        self.calls = 0

    def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        self.calls += 1
        refuse = self.calls <= self._refusals
        payload = PAYLOADS[output_model.__name__]

        async def events():
            if refuse:
                raise RuntimeError(f"{THROTTLE_MARK}: rate exceeded")
            yield {"output": output_model(**payload)}

        return events()


def row(schema: str, model_id: str, outcome: CallOutcome, sample: int = 1, **overrides) -> SweepRow:
    fields = dict(
        sample=sample,
        role="judge",
        output_schema=schema,
        model_id=model_id,
        outcome=outcome,
        latency_ms=100.0 * sample,
        input_tokens=10,
        output_tokens=5,
        estimated_usd=0.001,
    )
    return SweepRow(**{**fields, **overrides})


def test_every_schema_meets_every_model_the_fleet_is_configured_with():
    probes = build_registry()
    cases = build_cases(probes, sorted(configured_models()), 8)
    assert len(cases) == len(probes) * len(configured_models()) * 8
    assert len({(case.probe.name, case.model_id) for case in cases}) == len(probes) * 4


def test_the_cell_carries_the_interval_and_the_fields_that_were_rejected():
    rows = [
        row("OpenGrade", "model-a", CallOutcome.PARSED, 1),
        row("OpenGrade", "model-a", CallOutcome.PARSED, 2),
        row(
            "OpenGrade",
            "model-a",
            CallOutcome.MALFORMED,
            3,
            rejected_fields=["rubric_points (less_than_equal)"],
        ),
    ]
    report = build_matrix(rows, 3, "us-east-1", MEASURED_AT)
    cell = report.cells[0]
    assert (cell.calls, cell.parsed, cell.malformed) == (3, 2, 1)
    assert cell.parse_rate.low < 0.7 < cell.parse_rate.high
    assert cell.rejected_fields == {"rubric_points (less_than_equal)": 1}
    assert report.total_usd == pytest.approx(0.003)


def test_a_timed_out_call_reports_no_tokens_and_no_dollars():
    rows = [
        row("Snippet", "model-b", CallOutcome.TIMED_OUT, 1, input_tokens=0, output_tokens=0,
            estimated_usd=0.0)
    ]
    cell = build_matrix(rows, 1, "us-east-1", MEASURED_AT).cells[0]
    assert (cell.timed_out, cell.input_tokens, cell.estimated_usd) == (1, 0, 0.0)


async def test_a_throttled_call_is_retried_and_the_attempts_are_counted():
    probe = next(p for p in build_registry() if p.name == "OpenGrade")
    case = build_cases([probe], ["model-a"], 1)[0]
    model = ThrottlingModel(refusals=2)
    result = await run_case(case, model, RampClock(), sleep=_no_wait)
    assert result.outcome is CallOutcome.PARSED
    assert result.throttled_attempts == 2
    assert model.calls == 3


async def test_a_throttle_that_never_clears_is_recorded_rather_than_retried_forever():
    probe = next(p for p in build_registry() if p.name == "Snippet")
    case = build_cases([probe], ["model-a"], 1)[0]
    model = ThrottlingModel(refusals=MAX_THROTTLE_ATTEMPTS + 5)
    result = await run_case(case, model, RampClock(), sleep=_no_wait)
    assert result.outcome is CallOutcome.CALL_FAILED
    assert result.throttled_attempts == MAX_THROTTLE_ATTEMPTS


async def test_the_sweep_returns_one_row_per_case():
    probes = tuple(p for p in build_registry() if p.name in {"Snippet", "ProbeAnswer"})
    cases = build_cases(probes, list(MODELS), 2)
    models = {name: ThrottlingModel(refusals=0) for name in MODELS}
    rows = await run_sweep(cases, models, RampClock(), concurrency=2, announce=lambda _: None)
    assert len(rows) == len(cases)
    assert all(result.outcome is CallOutcome.PARSED for result in rows)


def test_the_matrix_table_names_every_cell_and_its_totals():
    rows = [row("Snippet", model_id, CallOutcome.PARSED) for model_id in MODELS]
    table = render_matrix(build_matrix(rows, 1, "us-east-1", MEASURED_AT))
    assert all(model_id in table for model_id in MODELS)
    assert "parsed 2/2" in table
    assert "0 throttled attempts" in table


async def _no_wait(_seconds: float) -> None:
    return None
