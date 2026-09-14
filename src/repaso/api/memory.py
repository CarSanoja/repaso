"""The memory observer is read-only and shares the existing judge allowlist."""

from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse

from repaso.api.judge import _allowed, _authorize, _container
from repaso.api.memory_episodes import learning_episodes
from repaso.api.memory_events import LocalEventFeed, owned_events
from repaso.api.memory_projection import project_memory

router = APIRouter(prefix="/judge/memory")
STATIC = Path(__file__).parent / "static"


@router.get("")
@router.get("/")
def page():
    return FileResponse(STATIC / "memory.html", headers={"Cache-Control": "no-store"})


@router.get("/assets/{name}")
def asset(name: str):
    if name not in {"memory.css", "memory.js"}:
        raise HTTPException(404)
    return FileResponse(STATIC / name)


@router.get("/snapshot/{family_id}")
def snapshot(
    family_id: str,
    request: Request,
    response: Response,
    x_judge_code: str | None = Header(default=None),
):
    container = _container(request)
    _authorize(container, x_judge_code)
    if not _allowed(container, family_id):
        raise HTTPException(404, "family_not_shared")
    response.headers["Cache-Control"] = "no-store"
    try:
        now = container.clock.now() if container.clock else None
        result, correlations = project_memory(container, family_id, now)
    except LookupError:
        raise HTTPException(404, "family_not_found") from None
    except Exception:
        raise HTTPException(503, "memory_unavailable") from None
    feed = getattr(request.app.state, "memory_events", None)
    if feed is None and container.settings.local_mode:
        feed = LocalEventFeed(container.settings.local_data_dir / "telemetry.jsonl")
    result["events"] = []
    rehearsal = getattr(request.app.state, "memory_rehearsal", None)
    result["rehearsal"] = bool(rehearsal)
    result["rehearsal_reset_available"] = callable(getattr(request.app.state, "memory_reset", None))
    result["rehearsal_completed"] = list(rehearsal.completed) if rehearsal else []
    result["events_status"] = "not_configured"
    if feed is not None:
        try:
            result["events"] = owned_events(feed.read(), family_id, correlations)
            result["events_status"] = "connected"
        except Exception:
            result["events_status"] = "unavailable"
    result["episodes"] = learning_episodes(
        result["notes"],
        result["events"],
        result.pop("_episode_deliveries", []),
        result.pop("_assessment_episodes", []),
    )
    return result


@router.post("/rehearsal/{step}")
async def rehearsal(step: str, request: Request, x_judge_code: str | None = Header(default=None)):
    container = _container(request)
    _authorize(container, x_judge_code)
    run = getattr(request.app.state, "memory_rehearsal", None)
    if not container.settings.local_mode or run is None:
        raise HTTPException(404)
    if step == "reset":
        reset = getattr(request.app.state, "memory_reset", None)
        if not callable(reset):
            raise HTTPException(404)
        async with run.lock:
            return await reset()
    if step not in {"help", "another", "answer", "reduce"}:
        raise HTTPException(422, "unsupported_step")
    try:
        return await run.step(step)
    except ValueError as error:
        raise HTTPException(409, str(error)) from None
