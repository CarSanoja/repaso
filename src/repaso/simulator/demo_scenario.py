from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from repaso.agents.capsule_composer import item_buttons
from repaso.channel.telegram.enrollment import CONSENT_YES
from repaso.config.models import ModelRole
from repaso.config.settings import Settings
from repaso.core.harness.clock import SimClock
from repaso.core.orchestration.context import Services
from repaso.core.orchestration.runner import active_session, current_item
from repaso.i18n import msg
from repaso.schemas.common import Lang
from repaso.schemas.item import ItemKind
from repaso.simulator.demo_followup import checkpoint, followup
from repaso.simulator.demo_ledger import close_ledger, harness_reading
from repaso.simulator.demo_material import (
    GUIDE_REF,
    GUIDE_TEXT,
    NOTEBOOK_REF,
    NOTEBOOK_TEXT,
)
from repaso.simulator.demo_stage import CHAT_REF, Stage, session_event
from repaso.simulator.demo_transcript import CHILD, PARENT, ScenarioResult
from repaso.simulator.notebook_image import render_notebook_png
from repaso.simulator.offline_services import assemble_services
from repaso.tools.llm import build_model, clear_cassette_cache
from repaso.tools.media_fetcher import INBOX_DIRNAME
from repaso.tools.media_store import normalize_ref

CASSETTE_PATH = Path(__file__).parent / "cassettes" / "demo_fracciones.jsonl"
START = datetime(2026, 9, 1, 22, 43, tzinfo=UTC)
INVITE_CODE = "REPASO-PILOTO-4B"
TELEGRAM = "telegram"
ANSWERS_EXPECTED = 3
QUARANTINE_PREFIX = "quar:"
REJECT_SUFFIX = ":no"
WRONG_ANSWER = "porque le sumé el mismo número arriba y abajo, así que valen igual"
HEDGED_ANSWER = "creo que sí porque los dos se parecen"
NOTEBOOK_CAPTION = "[foto: página del cuaderno de fracciones]"
GUIDE_CAPTION = "[foto: guía de refuerzo fotocopiada]"

ENROLMENT: tuple[tuple[str, dict[str, Any]], ...] = (
    (INVITE_CODE, {"text": INVITE_CODE}),
    ("Acepto", {"callback": CONSENT_YES}),
    ("Sofía Marín", {"text": "Sofía Marín"}),
    ("Sofi", {"text": "Sofi"}),
    ("4", {"text": "4"}),
    ("San José 4to B", {"text": "San José 4to B"}),
    ("7pm", {"text": "7pm"}),
)


def scenario_settings(data_dir: Path, cassette_path: Path | None = None) -> Settings:
    return Settings(
        local_mode=True,
        local_data_dir=data_dir,
        cassette_path=cassette_path or CASSETTE_PATH,
        pilot_invite_codes=INVITE_CODE,
    )


def build_scenario_services(settings: Settings) -> Services:
    return assemble_services(
        settings, SimClock(START), {role: build_model(role, settings) for role in ModelRole}
    )


def fill_inbox(settings: Settings) -> None:
    inbox = settings.local_data_dir / INBOX_DIRNAME
    for ref, text in ((NOTEBOOK_REF, NOTEBOOK_TEXT), (GUIDE_REF, GUIDE_TEXT)):
        path = inbox / normalize_ref(ref)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(render_notebook_png(text))


async def run_demo_scenario(
    settings: Settings,
    services: Services | None = None,
    decision: str = "teacher_note",
    stage_factory=None,
) -> ScenarioResult:
    clear_cassette_cache()
    fill_inbox(settings)
    stage = (stage_factory or Stage)(services or build_scenario_services(settings))
    await _enrol(stage)
    family = stage.services.store.find_family_by_chat(TELEGRAM, CHAT_REF)
    student = stage.services.store.list_students(family.id)[0]
    await _notebook(stage)
    checkpoint(stage, family, student, "Material revisado")
    await _open_session(stage, family, student)
    checkpoint(stage, family, student, "Práctica entregada")
    await _practice(stage, family, student)
    checkpoint(stage, family, student, "Respuesta pendiente de revisión")
    await _review(stage, family, student)
    checkpoint(stage, family, student, "Decisión humana aplicada")
    await _guide(stage)
    close_ledger(stage, family, student)
    await followup(stage, family, student, decision)
    return stage.result


async def _enrol(stage: Stage) -> None:
    route = ""
    for shown, fields in ENROLMENT:
        stage.clock.advance(minutes=1)
        route = (await stage.says(PARENT, shown, **fields)).get("route", "")
    stage.beat("enrolment ends with the family enrolled", "enrolled", route)
    warning = msg("alias_warning", Lang.ES)
    refused = any(record["text"] == warning for record in stage.outbox)
    stage.beat(
        "a name that looks real is refused as an alias", "refused", _yes_no(refused, "refused")
    )


async def _notebook(stage: Stage) -> None:
    stage.clock.advance(minutes=4)
    summary = await stage.says(PARENT, NOTEBOOK_CAPTION, media_ref=NOTEBOOK_REF)
    ingest = summary.get("ingest") or {}
    stage.beat("the notebook photo becomes practice", "material", summary.get("route"))
    stage.beat("questions written from the page", 6, ingest.get("generated"))
    stage.beat("questions that survived review", 5, len(ingest.get("kept_item_ids", [])))


async def _open_session(stage: Stage, family: Any, student: Any) -> None:
    stage.clock.advance(minutes=6)
    await stage.dispatch(session_event(family.id, student.id, stage.clock.now()))
    session = active_session(stage.services, student.id)
    planned = len(session.capsule.item_ids) if session and session.capsule else 0
    stage.beat("the capsule carries the day's three questions", 3, planned)


async def _practice(stage: Stage, family: Any, student: Any) -> None:
    opens = 0
    for index in range(1, ANSWERS_EXPECTED + 1):
        stage.clock.advance(minutes=1)
        session = active_session(stage.services, student.id)
        item = current_item(stage.services, session) if session else None
        if item is None:
            stage.beat(f"question {index} was waiting for an answer", "asked", "missing")
            return
        if item.kind is ItemKind.MCQ:
            choice = item.options.index(item.answer_key) + 1
            summary = await stage.says(
                CHILD,
                item.answer_key,
                callback=item_buttons(session.id, item)[choice - 1].callback_data,
            )
        else:
            answer = HEDGED_ANSWER if opens else WRONG_ANSWER
            opens += 1
            summary = await stage.says(CHILD, answer, text=answer)
        stage.note(
            f"after answer {index}",
            harness_reading(stage, family, student, item.id, summary),
        )


async def _review(stage: Stage, family: Any, student: Any) -> None:
    offered = stage.offered_button(QUARANTINE_PREFIX, REJECT_SUFFIX)
    stage.beat(
        "the answer the grader would not sign reaches the parent",
        "one tap",
        _yes_no(offered is not None, "one tap"),
    )
    if offered is None:
        stage.beat("the parent's tap settles it as wrong", "rejected", "never happened")
        return
    label, callback = offered
    stage.clock.advance(minutes=2)
    await stage.says(PARENT, label, callback=callback)
    quarantine_id = callback[len(QUARANTINE_PREFIX) :].partition(":")[0]
    record = stage.services.store.get_quarantine(family.id, quarantine_id)
    stage.beat("the parent's tap settles it as wrong", "rejected", record.status.value)
    released = str(record.payload.get("item_id", ""))
    stage.note(
        "after the parent's review",
        harness_reading(stage, family, student, released, {}),
    )


async def _guide(stage: Stage) -> None:
    stage.clock.advance(minutes=9)
    summary = await stage.says(PARENT, GUIDE_CAPTION, media_ref=GUIDE_REF)
    ingest = summary.get("ingest") or {}
    stage.beat("the guide's worked example is caught", "all_rejected", ingest.get("terminal"))
    stage.beat("nothing from the guide reaches the child", 0, len(ingest.get("kept_item_ids", [])))


def _yes_no(flag: bool, label: str) -> str:
    return label if flag else "never happened"
