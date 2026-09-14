"""Public synthetic demo: isolated visitor sessions, no production adapters or data."""

import asyncio
import os
import secrets
from collections import OrderedDict
from http.cookies import SimpleCookie
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from mangum import Mangum

from repaso.api import judge, memory
from repaso.api.dependencies import build_container
from repaso.config.settings import Settings
from repaso.simulator.memory_rehearsal import FAMILY_ID, MemoryRehearsal

COOKIE = "repaso_demo_session"
MAX_SESSIONS = 12
_ADAPTER = None


class DemoSession:
    def __init__(self, code):
        self.code = code
        self.root = None
        self.app = FastAPI(title="Repaso · Synthetic public demo", docs_url=None, redoc_url=None)
        # Inline the two assets to avoid parallel Lambda cold-start requests.
        for prefix, name in (("/judge/memory", "memory"), ("/judge", "judge")):
            page = self._page(name)

            def make_view(content):
                async def view():
                    return HTMLResponse(content, headers={"Cache-Control": "no-store"})

                return view

            self.app.add_api_route(prefix, make_view(page), methods=["GET"])
            self.app.add_api_route(prefix + "/", make_view(page), methods=["GET"])
        self.app.include_router(judge.router)
        self.app.include_router(memory.router)
        self.app.state.memory_reset = self.reset

    @staticmethod
    def _page(name):
        root = Path(memory.__file__).parent / "static"
        page = (root / f"{name}.html").read_text()
        prefix = "/judge/memory" if name == "memory" else "/judge"
        stylesheet = f'<link rel="stylesheet" href="{prefix}/assets/{name}.css">'
        script = f'<script src="{prefix}/assets/{name}.js" defer></script>'
        page = page.replace(stylesheet, "<style>" + (root / f"{name}.css").read_text() + "</style>")
        page = page.replace(script, "")
        page = page.replace(
            "</body>", "<script>" + (root / f"{name}.js").read_text() + "</script></body>"
        )
        return (
            page.replace("Local rehearsal · synthetic family", "Hosted demo · synthetic family")
            .replace("LOCAL REHEARSAL", "HOSTED DEMO")
            .replace("LOCAL · synthetic rehearsal", "HOSTED · synthetic rehearsal")
        )

    async def reset(self):
        root = TemporaryDirectory(prefix="repaso-public-demo-")
        settings = Settings(
            _env_file=None,
            local_mode=True,
            local_data_dir=Path(root.name),
            judge_family_ids=FAMILY_ID,
        )
        try:
            run = MemoryRehearsal(settings)
            await run.prepare()
            container = build_container(settings, judge_code=self.code)
            container.clock = run.clock
        except Exception:
            root.cleanup()
            raise
        previous = self.root
        self.root = root
        self.app.state.container = container
        self.app.state.memory_rehearsal = run
        if previous:
            previous.cleanup()
        return {"reset": True, "synthetic": True}

    def close(self):
        if self.root:
            self.root.cleanup()


class DemoSessions:
    """A bounded warm-container cache. Cold starts intentionally reset demonstration state."""

    def __init__(self, code=None, max_sessions=MAX_SESSIONS):
        self.code = code or os.environ.get("REPASO_DEMO_CODE", "REPASO-LIVE")
        self.max_sessions = max_sessions
        self.sessions = OrderedDict()
        self.lock = asyncio.Lock()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return
        path = scope.get("path", "/")
        if path == "/":
            await send(
                {
                    "type": "http.response.start",
                    "status": 307,
                    "headers": [(b"location", b"/judge/memory/"), (b"cache-control", b"no-store")],
                }
            )
            await send({"type": "http.response.body", "body": b""})
            return
        if not path.startswith("/judge"):
            await send({"type": "http.response.start", "status": 404, "headers": []})
            await send({"type": "http.response.body", "body": b"Not found"})
            return
        jar = SimpleCookie()
        try:
            for key, value in scope.get("headers", []):
                if key.lower() == b"cookie":
                    jar.load(value.decode("latin-1"))
            token = jar[COOKIE].value if COOKIE in jar else ""
        except Exception:
            token = ""
        # Serialize local state changes, reset and bounded-cache eviction.
        async with self.lock:
            session = self.sessions.get(token)
            if session is None:
                token = secrets.token_urlsafe(24)
                session = DemoSession(self.code)
                await session.reset()
                self.sessions[token] = session
                while len(self.sessions) > self.max_sessions:
                    _, retired = self.sessions.popitem(last=False)
                    retired.close()
            self.sessions.move_to_end(token)

            async def with_cookie(message):
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))
                    cookie = (
                        f"{COOKIE}={token}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=3600"
                    )
                    headers.append((b"set-cookie", cookie.encode("ascii")))
                    headers.append((b"cache-control", b"no-store"))
                    message = {**message, "headers": headers}
                await send(message)

            await session.app(scope, receive, with_cookie)


def handler(event, context=None):
    global _ADAPTER
    if _ADAPTER is None:
        _ADAPTER = Mangum(DemoSessions(), lifespan="off")
    return _ADAPTER(event, context)
