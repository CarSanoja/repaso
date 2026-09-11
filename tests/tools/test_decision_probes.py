import pytest

from repaso.config.models import ModelRole
from repaso.tools.guardrails import LocalScreener
from repaso.tools.llm import LocalPlaybackModel
from tests.live.agreement import REFUSED, run_decision, run_decision_probes
from tests.live.decisions import (
    INJECTED_MATERIAL,
    KNOWN_IDS,
    NOTHING,
    SAFE,
    UNLISTED,
    UNSAFE,
    build_decision_probes,
)
from tests.tools.live_fixtures import RampClock

PROBES = build_decision_probes()


def probe_named(fragment: str):
    return next(probe for probe in PROBES if fragment in probe.name)


def test_every_decision_has_an_expected_answer_its_reading_can_produce():
    assert len(PROBES) == 4
    for probe in PROBES:
        assert probe.expected
        assert probe.probe.role in set(ModelRole)


def test_the_probes_cover_the_two_roles_whose_output_is_a_closed_choice():
    assert {probe.role for probe in PROBES} == {ModelRole.CLASSIFY, ModelRole.STRUCTURED}


def test_the_injected_material_passes_the_deterministic_screener_untouched():
    assert LocalScreener().screen(INJECTED_MATERIAL).safe is True


def test_the_screen_reading_names_only_the_verdict():
    probe = probe_named("clean material")
    assert probe.reading(probe.probe.output_schema(safe=True, reasons=["nada"])) == SAFE
    assert probe.reading(probe.probe.output_schema(safe=False, reasons=["x"])) == UNSAFE


def test_the_mapping_reading_reports_an_id_outside_the_candidate_list_as_unlisted():
    probe = probe_named("competency")
    schema = probe.probe.output_schema
    assert probe.reading(schema(competency_ids=[KNOWN_IDS[0]])) == KNOWN_IDS[0]
    assert probe.reading(schema(competency_ids=["MAT-9-INVENTED"])) == UNLISTED
    assert probe.reading(schema(competency_ids=[])) == NOTHING


def test_the_policy_reading_reports_an_action_outside_the_vocabulary_as_unlisted():
    probe = probe_named("policy")
    schema = probe.probe.output_schema
    assert probe.reading(schema(action="continue", reason="r")) == "continue"
    assert probe.reading(schema(action="send_a_tutor", reason="r")) == UNLISTED


async def test_a_call_that_never_answers_is_recorded_as_unmet_rather_than_wrong():
    probe = probe_named("clean material")
    row = await run_decision(LocalPlaybackModel([]), probe, "model-a", 1, RampClock())
    assert row.answered is False
    assert row.answer == REFUSED
    assert row.met is False
    assert row.error == "PlaybackExhausted"


async def test_the_report_counts_agreement_with_the_expected_answer():
    probe = probe_named("policy")
    script = [{"action": "continue", "reason": "sigue"}, {"action": "reduce_load", "reason": "no"}]
    models = {"model-a": LocalPlaybackModel(script)}
    report = await run_decision_probes(
        [probe], models, 2, RampClock(), "us-east-1", announce=lambda _: None
    )
    cell = report.cells[0]
    assert (cell.calls, cell.met) == (2, 1)
    assert cell.answers == {"continue": 1, "reduce_load": 1}
    assert cell.agreement.point == pytest.approx(0.5)
