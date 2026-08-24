from hmac import compare_digest
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import FileResponse

from repaso.api.dependencies import AppContainer
from repaso.schemas.common import FamilyId, StrictBaseModel

CODE_HEADER = "X-Judge-Code"
STATIC_DIR = Path(__file__).parent / "static"
JUDGE_PAGE = STATIC_DIR / "judge.html"

router = APIRouter(prefix="/judge")


class JudgeLogin(StrictBaseModel):
    code: str


def _container(request: Request) -> AppContainer:
    return request.app.state.container


def _authorize(container: AppContainer, provided: str | None) -> None:
    if not container.judge_code:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="judge_code_not_configured"
        )
    if not provided or not compare_digest(provided, container.judge_code):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid_judge_code")


@router.post("/login")
async def login(payload: JudgeLogin, request: Request) -> dict[str, str]:
    container = _container(request)
    _authorize(container, payload.code)
    return {"token": payload.code}


@router.get("/students")
async def students(
    request: Request, x_judge_code: str | None = Header(default=None)
) -> list[dict[str, Any]]:
    container = _container(request)
    _authorize(container, x_judge_code)
    rows: list[dict[str, Any]] = []
    for family in container.store.list_families():
        for student in container.store.list_students(family.id):
            rows.append(
                {
                    "family_id": family.id,
                    "alias": student.alias,
                    "grade": student.grade,
                    "section_key": student.section_key,
                }
            )
    return rows


@router.get("/transcript/{family_id}")
async def transcript(
    family_id: str, request: Request, x_judge_code: str | None = Header(default=None)
) -> dict[str, list[dict[str, Any]]]:
    container = _container(request)
    _authorize(container, x_judge_code)
    key = FamilyId(family_id)
    return {
        "escalations": [
            item.model_dump(mode="json") for item in container.store.list_pending_escalations(key)
        ],
        "quarantine": [
            item.model_dump(mode="json") for item in container.store.list_pending_quarantine(key)
        ],
    }


@router.get("/")
async def page() -> FileResponse:
    return FileResponse(JUDGE_PAGE, media_type="text/html")
