import os
import subprocess
import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[2] / "infra" / "app.py"


@pytest.fixture(scope="session")
def assembly(tmp_path_factory) -> Path:
    pytest.importorskip("aws_cdk")
    outdir = tmp_path_factory.mktemp("cloud-assembly-shared")
    result = subprocess.run(
        [sys.executable, str(APP)],
        env={**os.environ, "CDK_OUTDIR": str(outdir)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return outdir
