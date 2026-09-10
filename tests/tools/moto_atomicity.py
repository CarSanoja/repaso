from threading import RLock
from typing import Any


class OneCallAtATime:
    def __init__(self, client: Any) -> None:
        self._client = client
        self._lock = RLock()

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._client, name)
        if not callable(attribute):
            return attribute

        def call(*args: Any, **kwargs: Any) -> Any:
            with self._lock:
                return attribute(*args, **kwargs)

        return call
