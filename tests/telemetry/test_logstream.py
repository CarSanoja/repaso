import json
import logging
from datetime import UTC, datetime

import pytest

from repaso.config.settings import Settings
from repaso.core.harness.clock import SimClock
from repaso.core.telemetry.logstream import HANDLER_NAME, TELEMETRY_LOGGER, telemetry_logger
from repaso.core.telemetry.sink import CloudWatchTelemetrySink, build_telemetry_sink

START = datetime(2026, 9, 12, 22, 30, tzinfo=UTC)


@pytest.fixture(autouse=True)
def clean_logger():
    logger = logging.getLogger(TELEMETRY_LOGGER)
    handlers = list(logger.handlers)
    logger.handlers.clear()
    yield
    logger.handlers[:] = handlers


def named(logger: logging.Logger) -> list[logging.Handler]:
    return [handler for handler in logger.handlers if handler.name == HANDLER_NAME]


def test_the_trace_logger_is_given_a_handler_of_its_own():
    logger = telemetry_logger()
    assert logger.level == logging.INFO
    assert named(logger)
    assert not logger.propagate


def test_a_second_call_does_not_double_the_handlers():
    first = telemetry_logger()
    assert telemetry_logger() is first
    assert len(named(first)) == 1


def test_the_deployed_sink_writes_every_trace_to_the_log_stream(tmp_path, capsys, monkeypatch):
    settings = Settings(aws_region="us-east-1", local_mode=False, local_data_dir=tmp_path)
    sink = build_telemetry_sink(settings, SimClock(START))
    assert isinstance(sink, CloudWatchTelemetrySink)
    monkeypatch.setattr(sink, "_namespace", "repaso")
    sink.trace("llm", "judge.structured", duration_ms=812.0, input_tokens="1200")
    printed = [line for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    assert len(printed) == 1
    logged = json.loads(printed[0])
    assert logged["kind"] == "llm"
    assert logged["name"] == "judge.structured"
    assert logged["duration_ms"] == 812.0
    assert logged["extra"]["input_tokens"] == "1200"
