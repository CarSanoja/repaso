from typing import Any

from fastapi import APIRouter, Request

from repaso.api.dependencies import AppContainer

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request) -> dict[str, Any]:
    container: AppContainer = request.app.state.container
    return {"status": "ready", "local_mode": bool(container.settings.local_mode)}
