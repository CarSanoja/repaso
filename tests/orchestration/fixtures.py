from datetime import UTC, datetime

from repaso.config.models import ModelRole
from repaso.core.harness.clock import SimClock
from repaso.core.orchestration.context import Services
from repaso.schemas.channel import ChannelKind, MediaKind
from repaso.schemas.common import Lang
from repaso.schemas.family import Family
from repaso.schemas.grading import EvidenceSpan
from repaso.schemas.item import Item, ItemKind, ItemStatus
from repaso.schemas.material import Material
from repaso.schemas.provenance import Provenance, Source
from repaso.schemas.review import HeldAnswer, QuarantineItem, QuarantineKind
from repaso.schemas.student import Student
from repaso.tools.event_bus import build_event_publisher
from repaso.tools.grade_log import build_grade_log
from repaso.tools.guardrails import build_screener
from repaso.tools.invite_codes import build_invite_codes
from repaso.tools.knowledge import build_knowledge_retriever
from repaso.tools.llm import LocalPlaybackModel
from repaso.tools.media_fetcher import build_media_fetcher
from repaso.tools.media_store import build_media_store
from repaso.tools.ocr import build_text_extractor
from repaso.tools.state_store import build_state_store
from repaso.tools.telegram import build_channel_sender

START = datetime(2026, 9, 1, 19, 0, tzinfo=UTC)
FRACTIONS = "math.g4.fractions.equivalence"


def make_services(settings, clock: SimClock | None = None) -> Services:
    clock = clock or SimClock(START)
    return Services(
        settings=settings,
        clock=clock,
        store=build_state_store(settings),
        grade_log=build_grade_log(settings, clock),
        media=build_media_store(settings),
        fetcher=build_media_fetcher(settings),
        extractor=build_text_extractor(settings),
        screener=build_screener(settings),
        retriever=build_knowledge_retriever(settings),
        publisher=build_event_publisher(settings),
        sender=build_channel_sender(settings),
        invites=build_invite_codes(settings),
        models={role: LocalPlaybackModel() for role in ModelRole},
    )


def seed_family(
    store, family_id: str = "f1", chat_ref: str = "100", section: str = "san-jose-4-b"
) -> tuple[Family, Student]:
    family = Family(
        id=family_id,
        channel=ChannelKind.TELEGRAM,
        chat_ref=chat_ref,
        lang=Lang.ES,
        invite_code="PILOT1",
        created_at=START,
    )
    student = Student(
        id=f"s-{family_id}",
        family_id=family_id,
        alias="Leo",
        grade=4,
        section_key=section,
        created_at=START,
    )
    store.put_family(family)
    store.put_student(student)
    return family, student


def make_material(family_id: str, material_id: str = "m1") -> Material:
    return Material(
        id=material_id,
        family_id=family_id,
        kind=MediaKind.PDF,
        media_ref=f"media/{material_id}",
        provenance=Provenance(source=Source.PARENT_UPLOAD, created_at=START),
    )


def seed_open_item(store, item_id: str = "i1") -> Item:
    item = Item(
        id=item_id,
        competency_id=FRACTIONS,
        kind=ItemKind.OPEN,
        difficulty=2,
        stem="Why is 2/4 the same as 1/2?",
        options=[],
        answer_key="both name the same amount",
        rationale="equivalence",
        rubric="2 points for equivalence reasoning",
        status=ItemStatus.ACTIVE,
        provenance=Provenance(source=Source.GENERATED, created_at=START),
    )
    store.put_item(item)
    return item


def seed_held_answer(
    store,
    family_id: str,
    student_id: str,
    item_id: str = "i1",
    quarantine_id: str = "q1",
    latency_seconds: float = 200.0,
) -> QuarantineItem:
    quarantine = QuarantineItem(
        id=quarantine_id,
        kind=QuarantineKind.LOW_CONFIDENCE_GRADE,
        family_id=family_id,
        evidence=EvidenceSpan(quote="la mitad", source_ref=f"response:{student_id}:{item_id}"),
        payload=HeldAnswer(
            item_id=item_id,
            student_id=student_id,
            answer="la mitad",
            latency_seconds=latency_seconds,
        ).model_dump(),
        created_at=START,
    )
    store.put_quarantine(quarantine)
    return quarantine


def mcq_draft(stem: str, answer: str, distractors: list[str]) -> dict:
    return {
        "kind": "mcq",
        "difficulty": 2,
        "stem": stem,
        "options": [answer, *distractors],
        "answer_key": answer,
        "rationale": "simplify both fractions",
        "rubric": None,
    }


def accepted_verdict() -> dict:
    return {"accepted": True, "flaws": [], "notes": ""}
