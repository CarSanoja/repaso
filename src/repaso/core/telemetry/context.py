from contextvars import ContextVar

invocation_context: ContextVar[dict | None] = ContextVar("repaso_invocation", default=None)
