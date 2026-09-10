import os
from pathlib import Path
from typing import Any

import pytest

from repaso.config.models import ModelRole
from repaso.config.settings import Settings
from repaso.core.harness.clock import SystemClock
from repaso.core.telemetry.sink import LocalTelemetrySink
from repaso.tools.call_ledger import LocalCallLedger
from repaso.tools.cost_report import build_cost_report
from repaso.tools.cost_table import render_cost_report
from repaso.tools.instrumented_model import instrument_models
from repaso.tools.llm import build_model
from tests.live.budget import BudgetEstimate, enforce_budget, estimate_budget
from tests.live.environment import LiveEnvironment, read_environment, skip_reason
from tests.live.registry import SchemaProbe, build_registry
from tests.live.reporter import TIMESTAMP_FORMAT, ConformanceReporter
from tests.live.routing import routing_model_ids

LIVE_DIR = Path(__file__).parent
REPORT_SUBDIR = "live"
TELEMETRY_FILE = "telemetry.jsonl"
LEDGER_PREFIX = "model-calls-"
LEDGER_SUFFIX = ".jsonl"

ENVIRONMENT: LiveEnvironment = read_environment(os.environ)
SKIP_REASON = skip_reason(ENVIRONMENT)

REPORTER_KEY = pytest.StashKey[ConformanceReporter]()
LEDGER_KEY = pytest.StashKey[LocalCallLedger]()


def live_settings_for(environment: LiveEnvironment) -> Settings:
    return Settings(aws_region=environment.region, local_mode=False, live_tests=True)


def report_directory(settings: Settings) -> Path:
    return settings.local_data_dir / REPORT_SUBDIR


def pytest_configure(config: pytest.Config) -> None:
    clock = SystemClock()
    directory = report_directory(live_settings_for(ENVIRONMENT))
    config.stash[REPORTER_KEY] = ConformanceReporter(clock, ENVIRONMENT.samples, directory)
    if SKIP_REASON is not None:
        return
    stamp = clock.now().strftime(TIMESTAMP_FORMAT)
    config.stash[LEDGER_KEY] = LocalCallLedger(
        directory / f"{LEDGER_PREFIX}{stamp}{LEDGER_SUFFIX}"
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    skip = pytest.mark.skip(reason=SKIP_REASON) if SKIP_REASON else None
    for item in items:
        if LIVE_DIR not in Path(str(item.fspath)).parents:
            continue
        item.add_marker(pytest.mark.live)
        if skip is not None:
            item.add_marker(skip)


def pytest_terminal_summary(terminalreporter: Any, config: pytest.Config) -> None:
    reporter = config.stash.get(REPORTER_KEY, None)
    if reporter is None or reporter.report().calls == 0:
        return
    path = reporter.write()
    terminalreporter.write_line("")
    for line in reporter.table().splitlines():
        terminalreporter.write_line(line)
    terminalreporter.write_line(f"written to {path}")
    ledger = config.stash.get(LEDGER_KEY, None)
    records = ledger.records() if ledger is not None else []
    if not records:
        return
    terminalreporter.write_line("")
    for line in render_cost_report(build_cost_report(records)).splitlines():
        terminalreporter.write_line(line)
    terminalreporter.write_line(f"ledger at {ledger.path}")


@pytest.fixture(scope="session")
def live_environment() -> LiveEnvironment:
    return ENVIRONMENT


@pytest.fixture(scope="session")
def live_settings(live_environment: LiveEnvironment) -> Settings:
    return live_settings_for(live_environment)


@pytest.fixture(scope="session")
def live_probes() -> tuple[SchemaProbe, ...]:
    return build_registry()


@pytest.fixture(scope="session", autouse=True)
def live_budget(
    live_probes: tuple[SchemaProbe, ...], live_environment: LiveEnvironment
) -> BudgetEstimate:
    return enforce_budget(
        estimate_budget(
            live_probes,
            routing_model_ids(),
            live_environment.samples,
            live_environment.budget_usd,
        )
    )


@pytest.fixture(scope="session")
def live_telemetry(live_settings: Settings) -> LocalTelemetrySink:
    return LocalTelemetrySink(report_directory(live_settings) / TELEMETRY_FILE, SystemClock())


@pytest.fixture(scope="session")
def live_ledger(pytestconfig: pytest.Config) -> LocalCallLedger:
    return pytestconfig.stash[LEDGER_KEY]


@pytest.fixture(scope="session")
def live_models(
    live_settings: Settings,
    live_telemetry: LocalTelemetrySink,
    live_ledger: LocalCallLedger,
) -> dict[ModelRole, Any]:
    return instrument_models(
        {role: build_model(role, live_settings) for role in ModelRole},
        live_telemetry,
        None,
        live_ledger,
        SystemClock(),
    )


@pytest.fixture(scope="session")
def live_reporter(pytestconfig: pytest.Config) -> ConformanceReporter:
    return pytestconfig.stash[REPORTER_KEY]
