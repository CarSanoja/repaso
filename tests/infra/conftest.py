import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[2] / "infra" / "app.py"
ALERT_EMAIL = "alerts@example.com"
STACKS = ("foundation", "messaging", "guardrails", "api", "agentcore", "observability")


def synthesize(outdir: Path, context: dict) -> Path:
    pytest.importorskip("aws_cdk")
    result = subprocess.run(
        [sys.executable, str(APP)],
        env={
            **os.environ,
            "CDK_OUTDIR": str(outdir),
            "CDK_CONTEXT_JSON": json.dumps({"alert_email": ALERT_EMAIL, **context}),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return outdir


def templates(assembly: Path) -> dict[str, dict]:
    return {
        name: json.loads((assembly / f"repaso-{name}.template.json").read_text(encoding="utf-8"))
        for name in STACKS
    }


@pytest.fixture(scope="session")
def assembly(tmp_path_factory) -> Path:
    return synthesize(tmp_path_factory.mktemp("cloud-assembly-shared"), {})


@pytest.fixture(scope="session")
def durable(tmp_path_factory) -> dict[str, dict]:
    return templates(synthesize(tmp_path_factory.mktemp("durable"), {}))


@pytest.fixture(scope="session")
def ephemeral(tmp_path_factory) -> dict[str, dict]:
    return templates(
        synthesize(tmp_path_factory.mktemp("ephemeral"), {"deployment_mode": "ephemeral"})
    )
