from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from repaso.api.dependencies import AppContainer, build_container
from repaso.api.main import create_app
from repaso.config.settings import Settings
from repaso.schemas.channel import ChannelKind
from repaso.schemas.escalation import Escalation, EscalationKind
from repaso.schemas.family import Family
from repaso.schemas.grading import EvidenceSpan
from repaso.schemas.review import QuarantineItem, QuarantineKind
from repaso.schemas.student import Student

TELEGRAM_SECRET = "testsecret"
JUDGE_CODE = "JUDGE1"
NOW = datetime(2026, 9, 1, 19, 0, tzinfo=UTC)
CHAT = {"id": 12345, "type": "private"}


@pytest.fixture
def api_settings(tmp_path) -> Settings:
    return Settings(local_mode=True, local_data_dir=tmp_path / "api_data", judge_family_ids="f1")


@pytest.fixture
def container(api_settings: Settings) -> AppContainer:
    return build_container(api_settings, telegram_secret=TELEGRAM_SECRET, judge_code=JUDGE_CODE)


@pytest.fixture
def app(container: AppContainer) -> FastAPI:
    return create_app(container)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


def make_update(text: str = "hola", update_id: int = 1) -> dict:
    return {
        "update_id": update_id,
        "message": {"message_id": 10, "chat": CHAT, "date": 1756750000, "text": text},
    }


def make_family(family_id: str = "f1", chat_ref: str = "12345") -> Family:
    return Family(
        id=family_id,
        channel=ChannelKind.TELEGRAM,
        chat_ref=chat_ref,
        invite_code="INV-1",
        created_at=NOW,
    )


def make_student(student_id: str = "s1", family_id: str = "f1") -> Student:
    return Student(
        id=student_id,
        family_id=family_id,
        alias="Ana",
        grade=5,
        section_key="5A",
        created_at=NOW,
    )


def make_escalation(escalation_id: str = "e1", family_id: str = "f1") -> Escalation:
    return Escalation(
        id=escalation_id,
        kind=EscalationKind.STRUGGLE_TRIAGE,
        family_id=family_id,
        summary="Ana falla fracciones",
        created_at=NOW,
    )


def make_quarantine(item_id: str = "q1", family_id: str = "f1") -> QuarantineItem:
    return QuarantineItem(
        id=item_id,
        kind=QuarantineKind.LOW_CONFIDENCE_GRADE,
        family_id=family_id,
        evidence=EvidenceSpan(quote="respuesta", source_ref="m1"),
        payload={"score": 0.4},
        created_at=NOW,
    )
