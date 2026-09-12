from datetime import UTC, datetime

import pytest

from repaso.tools.cloud_log_reader import read_messages, runtime_log_group

RUNTIME_ARN = "arn:aws:bedrock-agentcore:us-east-1:000000000000:runtime/repaso-pGH7rJ5W6n"
START = datetime(2026, 9, 12, 22, 0, tzinfo=UTC)
END = datetime(2026, 9, 12, 23, 0, tzinfo=UTC)


class FakeLogs:
    def __init__(self, pages: list[dict]) -> None:
        self.pages = pages
        self.requests: list[dict] = []

    def filter_log_events(self, **request):
        self.requests.append(request)
        return self.pages[len(self.requests) - 1]


class FakeSession:
    def __init__(self, logs: FakeLogs) -> None:
        self.logs = logs

    def client(self, name: str):
        assert name == "logs"
        return self.logs


def test_the_group_name_follows_the_runtime_id():
    assert runtime_log_group(RUNTIME_ARN) == (
        "/aws/bedrock-agentcore/runtimes/repaso-pGH7rJ5W6n-DEFAULT"
    )


def test_a_runtime_arn_without_an_id_is_refused():
    with pytest.raises(ValueError):
        runtime_log_group("arn:aws:bedrock-agentcore:us-east-1:000000000000:runtime/")


def test_every_page_of_the_window_is_read(monkeypatch):
    logs = FakeLogs(
        [
            {"events": [{"message": "first"}], "nextToken": "page-2"},
            {"events": [{"message": "second"}]},
        ]
    )
    monkeypatch.setattr("boto3.Session", lambda region_name: FakeSession(logs))
    assert read_messages("us-east-1", "group", START, END) == ["first", "second"]
    assert logs.requests[0]["startTime"] == int(START.timestamp() * 1000)
    assert logs.requests[0]["endTime"] == int(END.timestamp() * 1000)
    assert "nextToken" not in logs.requests[0]
    assert logs.requests[1]["nextToken"] == "page-2"
