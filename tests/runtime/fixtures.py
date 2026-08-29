from datetime import UTC, datetime

from repaso.config.models import ModelRole
from repaso.schemas.item import Item, ItemKind, ItemStatus
from repaso.schemas.provenance import Provenance, Source
from repaso.schemas.session import Capsule, PracticeSession, SessionStatus
from tests.orchestration.fixtures import FRACTIONS, accepted_verdict, mcq_draft

START = datetime(2026, 9, 1, 19, 0, tzinfo=UTC)
FRACTION_TEXT = (
    b"Equivalent fractions lesson: 2/4 equals 1/2 because both name the same amount. "
    b"Practice recognizing equivalent fractions with models."
)


def seed_item(store, item_id: str = "i1", kind: ItemKind = ItemKind.MCQ) -> Item:
    item = Item(
        id=item_id,
        competency_id=FRACTIONS,
        kind=kind,
        difficulty=2,
        stem="Which fraction equals 2/4?",
        options=["1/2", "2/8", "3/4"] if kind is ItemKind.MCQ else [],
        answer_key="1/2",
        rationale="both halves",
        rubric="2 points for equivalence reasoning" if kind is ItemKind.OPEN else None,
        status=ItemStatus.ACTIVE,
        provenance=Provenance(source=Source.GENERATED, created_at=START),
    )
    store.put_item(item)
    return item


def seed_session(services, student_id: str, item_ids: list[str]) -> PracticeSession:
    session = PracticeSession(
        id="sess1",
        student_id=student_id,
        session_date=services.clock.today(),
        capsule=Capsule(concept_snippet="snippet", item_ids=item_ids),
        status=SessionStatus.DELIVERED,
    )
    services.store.put_session(session)
    return session


def request(kind: str, family_id: str | None = None, **payload) -> dict:
    body: dict = {"kind": kind}
    if family_id is not None:
        body["family_id"] = family_id
    if payload:
        body["payload"] = payload
    return body


def script_ingest(services) -> None:
    services.models[ModelRole.CLASSIFY].enqueue({"safe": True, "reasons": []})
    services.models[ModelRole.STRUCTURED].enqueue({"competency_ids": [FRACTIONS]})
    services.models[ModelRole.GENERATE].enqueue(
        {
            "items": [
                mcq_draft("Which fraction equals 2/4?", "1/2", ["2/8", "3/4"]),
                mcq_draft("Which fraction equals 3/6?", "1/2", ["3/8", "2/3"]),
            ]
        }
    )
    for _ in range(2):
        services.models[ModelRole.JUDGE].enqueue(accepted_verdict())
        services.models[ModelRole.PROBE].enqueue({"answer": "no idea"})
