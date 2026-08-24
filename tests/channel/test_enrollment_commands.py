from datetime import UTC, datetime, time

import pytest

from repaso.channel.delivery import deliver, deliver_for_family
from repaso.channel.telegram.allowlist import is_known, pilot_codes, valid_invite
from repaso.channel.telegram.commands import handle_command, handle_forget_callback
from repaso.channel.telegram.enrollment import advance, parse_practice_time, start_enrollment
from repaso.i18n import msg
from repaso.schemas.channel import ChannelKind, InboundMessage, OutboundMessage
from repaso.schemas.common import Lang
from repaso.schemas.enrollment import EnrollmentStep
from repaso.schemas.family import FamilyStatus
from repaso.tools.state_store import build_state_store
from repaso.tools.telegram import LocalOutbox

CHAT = "12345"
CHANNEL = ChannelKind.TELEGRAM.value
NOW = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
CODES = frozenset({"PILOTO-1"})
ES = Lang.ES
YES = "consent:yes"
NO = "consent:no"


def inbound(text: str | None = None, callback: str | None = None) -> InboundMessage:
    return InboundMessage(
        channel=ChannelKind.TELEGRAM, chat_ref=CHAT, message_ref="m1", text=text,
        callback_data=callback, received_at=NOW,
    )


def begin(store):
    store.put_enrollment(start_enrollment(ChannelKind.TELEGRAM, CHAT, "PILOTO-1", ES))


def step(store, text=None, callback=None):
    return advance(store.get_enrollment(CHANNEL, CHAT), inbound(text, callback), store, NOW, CODES)


def said(reply, index: int = 0) -> str:
    return reply.messages[index].text


def at_alias(store):
    begin(store)
    step(store, callback=YES)


@pytest.fixture
def store(settings):
    return build_state_store(settings)


@pytest.fixture
def family(store):
    at_alias(store)
    for text in ("Leo", "4", "San José 4to B", "19:00"):
        step(store, text=text)
    return store.find_family_by_chat(CHANNEL, CHAT)


def test_full_enrollment_walk_creates_family_and_student(store):
    begin(store)
    opening = step(store, text="/start")
    assert [m.text for m in opening.messages] == [msg("welcome", ES), msg("consent", ES)]
    assert [b.callback_data for b in opening.messages[1].buttons] == [YES, NO]
    assert opening.messages[1].buttons[0].label == msg("consent_accept", ES)
    assert said(step(store, callback=YES)) == msg("ask_alias", ES)
    assert said(step(store, text="Leo")) == msg("ask_grade", ES)
    assert said(step(store, text="4")) == msg("ask_section", ES)
    assert said(step(store, text="San José 4to B")) == msg("ask_schedule", ES)
    final = step(store, text="7:30pm")
    assert final.done is True
    assert said(final) == msg("enrollment_done", ES, alias="Leo", time="19:30")
    assert said(final, 1) == msg("ask_first_material", ES, alias="Leo")
    enrolled = store.find_family_by_chat(CHANNEL, CHAT)
    student = store.list_students(enrolled.id)[0]
    assert enrolled.status is FamilyStatus.ACTIVE and enrolled.invite_code == "PILOTO-1"
    assert enrolled.practice_time == time(hour=19, minute=30)
    assert (enrolled.consent.version, enrolled.consent.chat_ref) == ("v1", CHAT)
    assert (student.alias, student.grade, student.section_key) == ("Leo", 4, "san-josé-4to-b")
    assert store.get_enrollment(CHANNEL, CHAT) is None


def test_consent_declined_deletes_progress(store):
    begin(store)
    reply = step(store, callback=NO)
    assert said(reply) == msg("consent_declined", ES)
    assert reply.done is False
    assert store.get_enrollment(CHANNEL, CHAT) is None


def test_real_name_alias_warns_then_nickname_is_accepted(store):
    at_alias(store)
    assert said(step(store, text="Juan Pérez")) == msg("alias_warning", ES)
    assert said(step(store, text="Mariafernandadelosangeles")) == msg("alias_warning", ES)
    assert store.get_enrollment(CHANNEL, CHAT).alias is None
    assert said(step(store, text="Campeón")) == msg("ask_grade", ES)
    progress = store.get_enrollment(CHANNEL, CHAT)
    assert progress.alias == "Campeón"
    assert progress.step is EnrollmentStep.GRADE


def test_bad_grade_and_schedule_answers_reask(store):
    at_alias(store)
    step(store, text="Leo")
    assert said(step(store, text="trece")) == msg("ask_grade", ES)
    assert said(step(store, text="15")) == msg("ask_grade", ES)
    assert store.get_enrollment(CHANNEL, CHAT).grade is None
    step(store, text="4")
    step(store, text="San José 4to B")
    reply = step(store, text="mañana")
    assert said(reply) == msg("ask_schedule", ES)
    assert reply.done is False
    assert store.list_families() == []
    assert store.get_enrollment(CHANNEL, CHAT).step is EnrollmentStep.SCHEDULE


def test_schedule_parser_accepts_common_formats():
    assert parse_practice_time("7pm") == (19, 0)
    assert parse_practice_time("19") == (19, 0)
    assert parse_practice_time("19:30") == (19, 30)
    assert parse_practice_time("7:30 pm") == (19, 30)
    assert parse_practice_time("12am") == (0, 0)
    assert parse_practice_time("mañana") is None
    assert parse_practice_time("25:00") is None


def test_allowlist_knows_families_enrollments_and_invite_codes(store, family):
    message = inbound(text="hola")
    assert is_known(message, store) is True
    store.forget_family(family.id)
    assert is_known(message, store) is False
    begin(store)
    assert is_known(message, store) is True
    codes = pilot_codes(" PILOTO-1, piloto-2 ,, ")
    assert codes == frozenset({"PILOTO-1", "piloto-2"})
    assert valid_invite(" piloto-1 ", codes) is True
    assert valid_invite("otro", codes) is False and valid_invite("", codes) is False


def test_pause_resume_and_language_toggles(store, family):
    assert said(handle_command(family, [], "/pause", store, NOW)) == msg("paused", ES)
    assert store.get_family(family.id).status is FamilyStatus.PAUSED
    resumed = handle_command(family, [], "/resume", store, NOW)
    assert said(resumed) == msg("resumed", ES, time="19:00")
    assert store.get_family(family.id).status is FamilyStatus.ACTIVE
    assert said(handle_command(family, [], "/language", store, NOW)) == msg("help", Lang.EN)
    assert store.get_family(family.id).lang is Lang.EN
    assert said(handle_command(family, [], "/language", store, NOW)) == msg("help", ES)


def test_status_reports_one_line_per_student(store, family):
    students = store.list_students(family.id)
    other = students[0].model_copy(update={"id": "s2", "alias": "Estrella"})
    reply = handle_command(family, [*students, other], "/status", store, NOW)
    assert len(reply.messages) == 2
    line = msg("status_line", ES, alias="Estrella", sessions="-", mastery_map="-", streak="-")
    assert said(reply, 1) == line


def test_unknown_command_and_exam_acknowledgement(store, family):
    assert handle_command(family, [], "hola bot", store, NOW) is None
    assert said(handle_command(family, [], "/inventado", store, NOW)) == msg("unknown_command", ES)
    assert said(handle_command(family, [], "/help", store, NOW)) == msg("help", ES)
    exam = handle_command(family, [], "/exam fracciones el viernes", store, NOW)
    assert said(exam) == msg("exam_ack", ES, competency="fracciones el viernes", date="")
    assert exam.events == []


def test_schedule_command_updates_practice_time(store, family):
    reply = handle_command(family, [], "/schedule 7:30pm", store, NOW)
    assert said(reply) == msg("resumed", ES, time="19:30")
    assert store.get_family(family.id).practice_time == time(hour=19, minute=30)
    assert said(handle_command(family, [], "/schedule", store, NOW)) == msg("ask_schedule", ES)
    late = handle_command(family, [], "/schedule mañana", store, NOW)
    assert said(late) == msg("ask_schedule", ES)


def test_forget_confirms_then_wipes_or_keeps(store, family):
    confirm = handle_command(family, [], "/forget", store, NOW)
    assert said(confirm) == msg("forget_confirm", ES)
    assert [b.callback_data for b in confirm.messages[0].buttons] == ["forget:yes", "forget:no"]
    kept = handle_forget_callback(family, store, ES, confirmed=False)
    assert said(kept) == msg("forget_keep", ES)
    assert store.get_family(family.id) is not None
    assert said(handle_forget_callback(family, store, ES)) == msg("forget_done", ES)
    assert store.get_family(family.id) is None
    assert store.list_students(family.id) == []


def test_delivery_stamps_family_chat_ref(family, tmp_path):
    stray = OutboundMessage(channel=ChannelKind.WEB, chat_ref="nowhere", text="hola")
    outbox = LocalOutbox(tmp_path)
    assert deliver_for_family([stray], family, outbox) == ["local:1"]
    assert outbox.sent[0]["chat_ref"] == CHAT
    assert stray.chat_ref == "nowhere"
    direct = [OutboundMessage(channel=ChannelKind.TELEGRAM, chat_ref=CHAT, text=t) for t in "ab"]
    assert deliver(direct, outbox) == ["local:2", "local:3"]
