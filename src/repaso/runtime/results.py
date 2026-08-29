from typing import Any

from repaso.runtime.errors import ErrorCode


def ok_result(kind: str, result: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "kind": kind, "result": result}


def error_result(code: ErrorCode, message: str, kind: str | None = None) -> dict[str, Any]:
    return {"ok": False, "kind": kind, "error": {"code": code.value, "message": message}}


def kind_hint(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    kind = payload.get("kind")
    return kind if isinstance(kind, str) else None
