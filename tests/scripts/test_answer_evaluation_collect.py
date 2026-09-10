from datetime import UTC, datetime
from pathlib import Path

from repaso.agents.prompts.grader import PROMPT_VERSION
from repaso.config.models import DEFAULT_MODELS, ModelRole
from repaso.tools.llm import LocalPlaybackModel
from scripts.answer_evaluation_collect import grade_case, provenance_of, sidecars
from scripts.run_answer_evaluation import read_cases

BATCH = Path("private/reports/evaluation-batch-1.jsonl")
NOW = datetime(2026, 9, 12, 10, tzinfo=UTC)


class SilentModel(LocalPlaybackModel):
    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        yield {"no_output": True}


def case_named(name: str) -> dict:
    cases = read_cases("evaluation/answer_review_set.jsonl")
    return next(case for case in cases if case["id"] == name)


def test_a_batch_records_the_model_prompt_and_commit_that_produced_it():
    record = provenance_of(
        [{"id": "eval-01-partial"}], "evaluation/answer_review_set.jsonl", "development"
    )
    assert record["model_id"] == DEFAULT_MODELS[ModelRole.JUDGE]
    assert record["prompt_version"] == PROMPT_VERSION
    assert record["case_ids"] == ["eval-01-partial"]
    assert record["split"] == "development"
    assert len(record["candidate_commit"]) == 40


def test_each_batch_keeps_its_own_ledger_telemetry_and_provenance():
    paths = sidecars(BATCH)
    assert paths["ledger"] == Path("private/reports/evaluation-batch-1.ledger.jsonl")
    assert paths["telemetry"] == Path("private/reports/evaluation-batch-1.telemetry.jsonl")
    assert paths["provenance"] == Path("private/reports/evaluation-batch-1.meta.json")
    assert len(set(paths.values())) == 3 and BATCH not in set(paths.values())


async def test_a_low_confidence_verdict_is_recorded_instead_of_discarded():
    model = LocalPlaybackModel(
        [{"correct": True, "rubric_points": 1.0, "confidence": 0.62, "feedback": "Bien."}]
    )
    row = await grade_case(case_named("eval-01-partial"), model, NOW)
    assert row["route"] == "graded" and row["correct"] is True
    assert row["confidence"] == 0.62 and row["rubric_points"] == 1.0


async def test_a_screened_answer_costs_no_call_and_carries_no_verdict():
    model = LocalPlaybackModel()
    row = await grade_case(case_named("eval-01-injection"), model, NOW)
    assert row["route"] == "screened" and row["correct"] is None
    assert row["confidence"] is None and model.calls == []


async def test_a_call_that_returns_nothing_is_recorded_as_a_failed_call():
    row = await grade_case(case_named("eval-01-partial"), SilentModel(), NOW)
    assert row["route"] == "call_failed" and row["correct"] is None
