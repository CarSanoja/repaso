import json
from typing import Any

from pydantic import BeforeValidator


def _decoded(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        parsed = json.loads(value)
    except ValueError:
        return value
    return parsed if isinstance(parsed, list) else value


JSON_TEXT_IS_LIST = BeforeValidator(_decoded)
