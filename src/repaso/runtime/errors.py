from enum import StrEnum


class ErrorCode(StrEnum):
    INVALID_PAYLOAD = "invalid_payload"
    UNKNOWN_KIND = "unknown_kind"
    UNSUPPORTED_KIND = "unsupported_kind"
    NOT_FOUND = "not_found"
    HANDLER_FAILED = "handler_failed"
    EVENT_LOOP_RUNNING = "event_loop_running"


class InvocationError(RuntimeError):
    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
