"""Collect real grader predictions for evaluation cases without exposing labels to the model."""

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from repaso.agents.grader import grade_open
from repaso.agents.prompts.grader import PROMPT_VERSION
from repaso.config.models import ModelRole, model_for
from repaso.config.settings import Settings
from repaso.core.harness.clock import SystemClock
from repaso.core.telemetry.sink import LocalTelemetrySink
from repaso.schemas.common import Lang
from repaso.schemas.grading import StudentResponse
from repaso.schemas.item import Item, ItemKind
from repaso.schemas.provenance import Provenance, Source
from repaso.tools.call_ledger import build_call_ledger
from repaso.tools.guardrails import LocalScreener
from repaso.tools.instrumented_model import InstrumentedModel
from repaso.tools.llm import build_model

ACCOUNT_ENV = "REPASO_EVALUATION_ACCOUNT_ID"
REGION = "us-east-1"
FAMILY = "evaluation-synthetic"
COMPETENCY = "math.g4.fractions.equivalence"
CONFIDENCE_THRESHOLD = 0.85


def sidecars(output: Path) -> dict[str, Path]:
    return {
        "ledger": output.with_suffix(".ledger.jsonl"),
        "telemetry": output.with_suffix(".telemetry.jsonl"),
        "provenance": output.with_suffix(".meta.json"),
    }


def candidate_commit() -> str:
    done = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return done.stdout.strip() if done.returncode == 0 else "unknown"


def provenance_of(cases: list[dict], dataset: str, split: str) -> dict:
    return {
        "dataset": dataset,
        "split": split,
        "case_ids": [case["id"] for case in cases],
        "role": ModelRole.JUDGE.value,
        "model_id": model_for(ModelRole.JUDGE),
        "prompt_version": PROMPT_VERSION,
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "candidate_commit": candidate_commit(),
        "region": REGION,
        "collected_at": datetime.now(UTC).isoformat(),
    }


def judge_model(output: Path):
    paths = sidecars(output)
    settings = Settings(
        local_mode=False,
        aws_region=REGION,
        local_data_dir=output.parent,
        call_ledger_path=paths["ledger"],
    )
    return InstrumentedModel(
        build_model(ModelRole.JUDGE, settings),
        ModelRole.JUDGE.value,
        LocalTelemetrySink(paths["telemetry"], SystemClock()),
        ledger=build_call_ledger(settings),
    )


def assert_authorized_account() -> None:
    import boto3

    expected = os.environ.get(ACCOUNT_ENV, "").strip()
    if not expected:
        raise ValueError(f"set {ACCOUNT_ENV} to the authorized account")
    os.environ["AWS_PROFILE"] = "quanta"
    session = boto3.Session(profile_name="quanta", region_name=REGION)
    if session.client("sts").get_caller_identity()["Account"] != expected:
        raise ValueError("evaluation must stay in the authorized account")


async def collect(
    cases: list[dict], output: Path, max_calls: int, dataset: str, split: str
) -> list[dict]:
    assert_authorized_account()
    chosen = cases[:max_calls]
    sidecars(output)["provenance"].write_text(
        json.dumps(provenance_of(chosen, dataset, split), indent=2)
    )
    model = judge_model(output)
    predictions = []
    for case in chosen:
        now = datetime.now(UTC)
        row = {"id": case["id"], "origin": "live", "at": now.isoformat()}
        try:
            if not LocalScreener().screen(case["answer"]).safe:
                row.update(correct=None, quarantined=True, confidence=None, route="screened")
            else:
                item = Item(
                    id=case["id"],
                    family_id=FAMILY,
                    kind=ItemKind.OPEN,
                    competency_id=COMPETENCY,
                    difficulty=2,
                    stem=case["question"],
                    answer_key=case["answer_key"],
                    rubric=case["rubric"],
                    rationale=case["answer_key"],
                    provenance=Provenance(source=Source.SIMULATED, created_at=now),
                )
                response = StudentResponse(
                    student_id=FAMILY,
                    item_id=item.id,
                    text=case["answer"],
                    latency_seconds=45,
                    received_at=now,
                )
                grade, _ = await grade_open(
                    item, response, Lang.ES, model, CONFIDENCE_THRESHOLD, now, FAMILY
                )
                row.update(
                    correct=grade.correct,
                    quarantined=grade.quarantined,
                    confidence=grade.confidence,
                    rubric_points=grade.rubric_points,
                )
        except Exception as error:
            row["error"] = type(error).__name__
        predictions.append(row)
        with output.open("a") as file:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
        if row.get("error"):
            break
    return predictions
