import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROBE = Path(__file__).resolve().parent / "import_probe.py"
REPO_ROOT = PROBE.parents[1]
MUST_COVER = (
    "repaso.api.main",
    "repaso.core.orchestration.channel_runner",
    "repaso.lambdas.worker",
    "repaso.runtime.entrypoint",
    "repaso.tools.llm",
    "repaso.tools.media_fetcher",
    "repaso.tools.state_dynamo",
    "repaso.tools.telegram_media",
)
DEPLOYED = {"REPASO_LOCAL_MODE": "false", "REPASO_AWS_REGION": "us-east-1"}


@pytest.fixture(scope="module")
def probed() -> dict:
    environment = {k: v for k, v in os.environ.items() if not k.startswith("REPASO_")}
    result = subprocess.run(
        [sys.executable, str(PROBE)],
        cwd=REPO_ROOT,
        env={**environment, **DEPLOYED},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_the_probe_reaches_every_module_a_deployment_would_load(probed):
    assert not probed["failed"]
    assert set(MUST_COVER) <= set(probed["imported"])


def test_no_module_opens_an_aws_or_http_client_while_being_imported(probed):
    assert probed["opened"] == []


def test_no_module_drags_the_cdk_into_the_running_application(probed):
    assert probed["cloud_sdks"] == []
