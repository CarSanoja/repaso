import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from repaso.tools.call_cost import cost_for
from repaso.tools.call_ledger import CallOrigin, CallOutcome, CallRecord, LocalCallLedger
from repaso.tools.model_usage import CallUsage

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "run_cost_report.py"
SONNET = "us.anthropic.claude-sonnet-4-6"


def seed(path: Path) -> None:
    ledger = LocalCallLedger(path)
    for number, usage in enumerate(
        (
            CallUsage(input_tokens=671, output_tokens=37),
            CallUsage(input_tokens=15, output_tokens=4, cache_read_tokens=3723),
            None,
        ),
        start=1,
    ):
        ledger.append(
            CallRecord(
                call_id=f"c{number}",
                at=datetime(2026, 9, 12, 9, number, tzinfo=UTC),
                role="judge",
                model_id=SONNET,
                kind="structured_output",
                output_model="OpenGrade",
                origin=CallOrigin.LIVE,
                outcome=CallOutcome.OK if usage else CallOutcome.FAILED,
                latency_ms=float(number * 100),
                usage=usage,
                cost=None if usage is None else cost_for(SONNET, usage),
            )
        )


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def test_the_script_prints_the_spend_and_writes_the_report(tmp_path):
    ledger = tmp_path / "calls.jsonl"
    seed(ledger)
    report = tmp_path / "report.json"

    result = run("--ledger", str(ledger), "--json", str(report))

    assert result.returncode == 0, result.stderr
    assert "by role" in result.stdout and "by model" in result.stdout
    assert "cache hit savings: $0.0101" in result.stdout
    assert "reasoning tokens: not reported" in result.stdout
    assert "1 of 3 without reported usage" in result.stdout
    assert "p95 ms" in result.stdout

    written = json.loads(report.read_text(encoding="utf-8"))
    assert written["calls"] == 3
    assert written["reported"] == 2
    assert written["usage"]["cache_read_tokens"] == 3723


def test_the_script_names_a_ledger_it_cannot_read(tmp_path):
    result = run("--ledger", str(tmp_path / "absent.jsonl"))

    assert result.returncode == 1
    assert "not found" in result.stderr
