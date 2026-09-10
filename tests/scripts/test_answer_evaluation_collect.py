from pathlib import Path

from repaso.agents.prompts.grader import PROMPT_VERSION
from repaso.config.models import DEFAULT_MODELS, ModelRole
from scripts.answer_evaluation_collect import provenance_of, sidecars

BATCH = Path("private/reports/evaluation-batch-1.jsonl")


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
