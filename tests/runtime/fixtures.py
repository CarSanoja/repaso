from datetime import UTC, datetime
from uuid import uuid4

from repaso.config.models import ModelRole
from repaso.config.settings import Settings
from repaso.runtime import invoke
from repaso.schemas.channel import ChannelKind, InboundMedia, InboundMessage
from repaso.schemas.item import Item, ItemKind, ItemStatus
from repaso.schemas.provenance import Provenance, Source
from repaso.schemas.session import Capsule, PracticeSession, SessionStatus
from repaso.tools.call_quota import build_call_quota
from repaso.tools.instrumented_model import instrument_models
from repaso.tools.model_limits import ModelLimits
from tests.orchestration.fixtures import FRACTIONS, accepted_verdict, make_services, mcq_draft

START = datetime(2026, 9, 1, 19, 0, tzinfo=UTC)
INVITE_CODE = "PILOTO-1"
NEW_CHAT = "9001"
FAMILY_CHAT = "100"
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


def seed_session(
    services, student_id: str, item_ids: list[str], delivered_at: datetime | None = None
) -> PracticeSession:
    session = PracticeSession(
        id="sess1",
        student_id=student_id,
        session_date=services.clock.today(),
        capsule=Capsule(concept_snippet="snippet", item_ids=item_ids),
        status=SessionStatus.DELIVERED,
        delivered_at=delivered_at,
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


def pilot_settings(settings, codes: str = INVITE_CODE) -> Settings:
    return Settings(
        local_mode=True, local_data_dir=settings.local_data_dir, pilot_invite_codes=codes
    )


def inbound(
    text: str | None = None,
    callback: str | None = None,
    media: InboundMedia | None = None,
    chat_ref: str = NEW_CHAT,
    message_ref: str | None = None,
    received_at: datetime = START,
) -> InboundMessage:
    return InboundMessage(
        channel=ChannelKind.TELEGRAM,
        chat_ref=chat_ref,
        message_ref=message_ref or uuid4().hex,
        text=text,
        callback_data=callback,
        media=media,
        received_at=received_at,
    )


def channel_request(message: InboundMessage) -> dict:
    return {
        "kind": "channel_message",
        "idempotency_key": f"{message.chat_ref}#{message.message_ref}",
        "occurred_at": message.received_at.isoformat(),
        "payload": message.model_dump(mode="json"),
    }


def pilot(settings):
    return make_services(pilot_settings(settings))


def bounded_pilot(settings, **limits):
    services = make_services(
        Settings(
            local_mode=True,
            local_data_dir=settings.local_data_dir,
            pilot_invite_codes=INVITE_CODE,
            **limits,
        )
    )
    inner = dict(services.models)
    services.models = instrument_models(
        inner,
        services.telemetry,
        ModelLimits(
            services.settings, services.store, services.clock, build_call_quota(services.settings)
        ),
    )
    return services, inner


def model_calls(inner) -> int:
    return sum(len(model.calls) for model in inner.values())


def send(services, message) -> dict:
    return invoke(channel_request(message), services)


def route_of(response: dict) -> str:
    assert response["ok"] is True, response
    return response["result"]["route"]


def texts(response: dict) -> list[str]:
    return [message["text"] for message in response["result"]["outbound"]]
