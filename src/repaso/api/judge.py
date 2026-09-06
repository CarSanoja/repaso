from hmac import compare_digest
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import FileResponse

from repaso.api.dependencies import AppContainer
from repaso.schemas.common import FamilyId, StrictBaseModel
from repaso.tools.grade_log import build_grade_log, effective_grades

CODE_HEADER = "X-Judge-Code"
STATIC_DIR = Path(__file__).parent / "static"
JUDGE_PAGE = STATIC_DIR / "judge.html"

router = APIRouter(prefix="/judge")


class JudgeLogin(StrictBaseModel):
    code: str


class DemoRequest(StrictBaseModel):
    decision: str = "teacher_note"


def _allowed(container, family_id):
    return family_id in {
        s.strip() for s in container.settings.judge_family_ids.split(",") if s.strip()
    }


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
        if not _allowed(container, family.id):
            continue
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
    if not _allowed(container, family_id):
        raise HTTPException(status_code=404, detail="family_not_shared")
    key = FamilyId(family_id)
    people = container.store.list_students(key)
    grades = build_grade_log(container.settings)
    return {
        "materials": [m.model_dump(mode="json") for m in container.store.list_materials(key)],
        "sessions": [
            s.model_dump(mode="json") for p in people for s in container.store.list_sessions(p.id)
        ],
        "grades": [
            g.model_dump(mode="json")
            for p in people
            for g in effective_grades(grades.by_student(p.id))
        ],
        "mastery": [
            m.model_dump(mode="json") for p in people for m in container.store.list_mastery(p.id)
        ],
        "delivery": [r.payload for r in container.store.list_records(key, "outbox#")],
        "escalations": [
            item.model_dump(mode="json") for item in container.store.list_escalations(key)
        ],
        "quarantine": [
            item.model_dump(mode="json") for item in container.store.list_quarantine(key)
        ],
    }


@router.post("/demo/run")
async def demo(
    payload: DemoRequest, request: Request, x_judge_code: str | None = Header(default=None)
) -> dict:
    _authorize(_container(request), x_judge_code)
    if payload.decision not in {"teacher_note", "reduce_load"}:
        raise HTTPException(status_code=422, detail="unsupported_decision")
    from dataclasses import asdict
    from tempfile import TemporaryDirectory

    from repaso.simulator.demo_scenario import run_demo_scenario, scenario_settings

    # A separate temporary state store: no production families, channel sends,
    # credentials, or paid models are reachable from these controls.
    with TemporaryDirectory(prefix="repaso-judge-") as root:
        result = await run_demo_scenario(scenario_settings(Path(root)), decision=payload.decision)
    return {
        "origin": "authored simulation",
        "live_inference": False,
        "decision": payload.decision,
        "passed": not result.failures,
        "checks": len(result.beats),
        **asdict(result),
    }


@router.get("")
@router.get("/")
async def page() -> FileResponse:
    return FileResponse(JUDGE_PAGE, media_type="text/html")


@router.get("/assets/{name}")
async def asset(name: str) -> FileResponse:
    allowed = {"judge.css": "text/css", "judge.js": "application/javascript"}
    if name not in allowed:
        raise HTTPException(status_code=404)
    return FileResponse(STATIC_DIR / name, media_type=allowed[name])
