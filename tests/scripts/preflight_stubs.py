import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

SCRIPTS = str(Path(__file__).resolve().parents[2] / "scripts")


def load(name: str) -> ModuleType:
    if SCRIPTS not in sys.path:
        sys.path.insert(0, SCRIPTS)
    return importlib.import_module(name)


class AwsError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class StubClient:
    def __init__(self, answers: dict[str, Any]) -> None:
        self._answers = answers
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __getattr__(self, method: str):
        def call(**kwargs: Any) -> Any:
            self.calls.append((method, kwargs))
            answer = self._answers.get(method)
            if isinstance(answer, Exception):
                raise answer
            if callable(answer):
                return answer(**kwargs)
            if answer is None:
                raise AwsError("ResourceNotFoundException")
            return answer

        return call


class StubSession:
    def __init__(self, clients: dict[str, StubClient], region_name: str = "us-east-1") -> None:
        self._clients = clients
        self.region_name = region_name
        self.asked: list[str] = []

    def client(self, service_name: str, **kwargs: Any) -> StubClient:
        self.asked.append(service_name)
        return self._clients.get(service_name, StubClient({}))
