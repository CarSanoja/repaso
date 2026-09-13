from datetime import UTC, date, datetime

import pytest

from repaso.channel.telegram.commands import handle_command
from repaso.channel.telegram.exam_dates import parse_exam_date, split_exam_argument
from repaso.i18n import counted, msg
from repaso.schemas.channel import ChannelKind
from repaso.schemas.common import Lang
from repaso.schemas.events import EventKind
from repaso.schemas.family import Family
from repaso.schemas.mastery import MasteryLevel, MasteryState
from repaso.schemas.student import Student
from repaso.tools.state_store import build_state_store

NOW = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
TODAY = NOW.date()
ES = Lang.ES
CHAT = "12345"


@pytest.fixture
def store(settings):
    return build_state_store(settings)


@pytest.fixture
def family(store):
    family = Family(
        id="f1",
        channel=ChannelKind.TELEGRAM,
        chat_ref=CHAT,
        lang=ES,
        invite_code="PILOTO-1",
        created_at=NOW,
    )
    store.put_family(family)
    store.put_student(
        Student(
            id="s1",
            family_id="f1",
            alias="Leo",
            grade=4,
            section_key="san-jose-4-b",
            created_at=NOW,
        )
    )
    return family


def said(reply, index: int = 0) -> str:
    return reply.messages[index].text


def mastery(competency_id: str, level: MasteryLevel, attempts: int, streak: int) -> MasteryState:
    return MasteryState(
        student_id="s1",
        competency_id=competency_id,
        ema_accuracy=0.5,
        attempts=attempts,
        correct=attempts // 2,
        streak=streak,
        level=level,
    )


def test_parser_accepts_the_four_written_formats():
    assert parse_exam_date("12-09", TODAY) == date(2026, 9, 12)
    assert parse_exam_date("12/09", TODAY) == date(2026, 9, 12)
    assert parse_exam_date("12-09-2026", TODAY) == date(2026, 9, 12)
    assert parse_exam_date("2026-09-12", TODAY) == date(2026, 9, 12)


def test_bare_day_and_month_roll_into_the_next_year_when_already_past():
    assert parse_exam_date("01-01", TODAY) == date(2027, 1, 1)
    assert parse_exam_date("20-08", TODAY) == TODAY


def test_parser_rejects_garbage():
    for token in ("viernes", "", "32-13", "2026", "12-09-", "mañana"):
        assert parse_exam_date(token, TODAY) is None


def test_split_takes_the_date_out_of_the_free_text():
    assert split_exam_argument("fracciones 12/09", TODAY) == ("fracciones", date(2026, 9, 12))
    assert split_exam_argument("el examen de mate", TODAY) is None


def test_exam_stores_a_date_per_student_and_emits_the_event(store, family):
    reply = handle_command(family, store.list_students("f1"), "/exam fracciones 12/09", store, NOW)

    assert said(reply) == msg("exam_ack", ES, competency="fracciones", date="12/09")
    stored = store.list_exam_dates("s1")
    assert [exam.exam_date for exam in stored] == [date(2026, 9, 12)]
    assert stored[0].competency_id is None
    event = reply.events[0]
    assert event.kind is EventKind.EXAM_ANNOUNCED
    assert event.family_id == "f1"
    assert event.idempotency_key == "exam#f1#2026-09-12"
    assert event.payload == {"exam_date": "2026-09-12", "topic": "fracciones"}


def test_exam_without_a_readable_date_asks_again_and_stores_nothing(store, family):
    reply = handle_command(family, store.list_students("f1"), "/exam el viernes", store, NOW)

    assert said(reply) == msg("exam_ask_date", ES)
    assert reply.events == []
    assert store.list_exam_dates("s1") == []


def test_forget_erases_the_exam_dates(store, family):
    handle_command(family, store.list_students("f1"), "/exam fracciones 12/09", store, NOW)
    store.forget_family("f1")
    assert store.list_exam_dates("s1") == []


def test_status_reports_the_counts_behind_every_claim(store, family):
    store.put_mastery(mastery("c1", MasteryLevel.MASTERED, attempts=6, streak=3))
    store.put_mastery(mastery("c2", MasteryLevel.DEVELOPING, attempts=4, streak=1))
    store.put_mastery(mastery("c3", MasteryLevel.STRUGGLING, attempts=2, streak=-2))

    reply = handle_command(family, store.list_students("f1"), "/status", store, NOW)

    summary = msg("progress_summary", ES, holds=0, needs_help=0, unknown=3)
    assert said(reply) == msg(
        "status_line",
        ES,
        alias="Leo",
        answers=counted("status_answers", ES, 12),
        correct=counted("status_correct", ES, 6),
        topics=counted("status_topics", ES, 3),
        days=counted("status_days", ES, 0),
        progress_map=summary,
    )
    assert "-" not in said(reply)


def test_a_never_measured_topic_is_not_reported_as_going_well(store, family):
    store.put_mastery(mastery("c1", MasteryLevel.UNKNOWN, attempts=2, streak=1))

    said_text = said(handle_command(family, store.list_students("f1"), "/status", store, NOW))

    assert "1 aún sin medir" in said_text
    assert said_text.startswith("Leo: 2 preguntas respondidas, 1 correcta, en 1 tema,")


def test_status_never_claims_a_topic_is_mastered(store, family):
    store.put_mastery(
        MasteryState(
            student_id="s1",
            competency_id="c1",
            ema_accuracy=0.95,
            attempts=3,
            correct=3,
            streak=3,
            level=MasteryLevel.MASTERED,
        )
    )

    said_text = said(handle_command(family, store.list_students("f1"), "/status", store, NOW))

    assert "domin" not in said_text.lower()
    assert "1 aún sin medir" in said_text


def test_status_without_history_shows_zeros_instead_of_placeholders(store, family):
    reply = handle_command(family, store.list_students("f1"), "/status", store, NOW)

    summary = msg("progress_summary", ES, holds=0, needs_help=0, unknown=0)
    assert said(reply) == msg(
        "status_line",
        ES,
        alias="Leo",
        answers=counted("status_answers", ES, 0),
        correct=counted("status_correct", ES, 0),
        topics=counted("status_topics", ES, 0),
        days=counted("status_days", ES, 0),
        progress_map=summary,
    )
