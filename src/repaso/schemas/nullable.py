from typing import Any

from pydantic import BeforeValidator


def _empty_when_null(value: Any) -> Any:
    return [] if value is None else value


def _blank_when_null(value: Any) -> Any:
    return "" if value is None else value


NULL_IS_EMPTY = BeforeValidator(_empty_when_null)
NULL_IS_BLANK = BeforeValidator(_blank_when_null)
