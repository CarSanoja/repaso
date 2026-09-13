from dataclasses import dataclass, field
from datetime import date, datetime, time

from repaso.channel.telegram.enrollment import parse_practice_time
from repaso.channel.telegram.exam_dates import split_exam_argument
from repaso.core.harness.progress import ProgressReadout, read_progress
from repaso.i18n import msg
from repaso.schemas.channel import Button, OutboundMessage
from repaso.schemas.common import Lang
from repaso.schemas.events import DomainEvent, EventKind
from repaso.schemas.family import Family, FamilyStatus
from repaso.schemas.mastery import MasteryState
from repaso.schemas.schedule import ExamDate
from repaso.schemas.student import Student
from repaso.tools.state_store import StateStore

FORGET_YES = "forget:yes"
FORGET_NO = "forget:no"


@dataclass
class CommandReply:
    messages: list[OutboundMessage]
    events: list[DomainEvent] = field(default_factory=list)


def handle_command(
    family: Family,
    students: list[Student],
    text: str,
    store: StateStore,
    now: datetime,
) -> CommandReply | None:
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None
    head, _, argument = stripped.partition(" ")
    command = head.split("@")[0].lower()
    argument = argument.strip()
    if command == "/help":
        return _single(family, "help")
    if command == "/pause":
        return _set_status(family, store, FamilyStatus.PAUSED, "paused")
    if command == "/resume":
        return _set_status(family, store, FamilyStatus.ACTIVE, "resumed")
    if command == "/language":
        return _toggle_language(family, store)
    if command == "/status":
        return _status(family, students, store)
    if command == "/schedule":
        return _schedule(family, store, argument)
    if command == "/exam":
        return _exam(family, students, store, argument, now)
    if command == "/forget":
        return _forget_prompt(family)
    return _single(family, "unknown_command")


def handle_forget_callback(
    family: Family, store: StateStore, lang: Lang, confirmed: bool = True
) -> CommandReply:
    if not confirmed:
        return _single(family, "forget_keep", lang=lang)
    store.forget_family(family.id)
    return _single(family, "forget_done", lang=lang)


def _out(
    family: Family,
    key: str,
    buttons: list[Button] | None = None,
    lang: Lang | None = None,
    **kwargs: object,
) -> OutboundMessage:
    return OutboundMessage(
        channel=family.channel,
        chat_ref=family.chat_ref,
        text=msg(key, lang or family.lang, **kwargs),
        buttons=buttons or [],
    )


def _single(
    family: Family, key: str, lang: Lang | None = None, **kwargs: object
) -> CommandReply:
    return CommandReply(messages=[_out(family, key, None, lang, **kwargs)])


def _stamp(value: time) -> str:
    return value.strftime("%H:%M")


def _set_status(
    family: Family, store: StateStore, status: FamilyStatus, key: str
) -> CommandReply:
    family.status = status
    store.put_family(family)
    if key == "resumed":
        return _single(family, key, time=_stamp(family.practice_time))
    return _single(family, key)


def _toggle_language(family: Family, store: StateStore) -> CommandReply:
    family.lang = Lang.EN if family.lang is Lang.ES else Lang.ES
    store.put_family(family)
    return _single(family, "help")


def _status(family: Family, students: list[Student], store: StateStore) -> CommandReply:
    return CommandReply(
        messages=[
            _status_line(family, student, store.list_mastery(student.id))
            for student in students
        ]
    )


def _status_line(family: Family, student: Student, states: list[MasteryState]) -> OutboundMessage:
    readout = read_progress(states)
    return _out(
        family,
        "status_line",
        None,
        None,
        alias=student.alias,
        answers=readout.answers,
        correct=readout.correct,
        topics=readout.practised,
        progress_map=_progress_summary(readout, family.lang),
    )


def _progress_summary(readout: ProgressReadout, lang: Lang) -> str:
    return msg(
        "progress_summary",
        lang,
        holds=readout.holds,
        needs_help=readout.needs_help,
        unknown=readout.not_yet_known,
    )


def _exam(
    family: Family,
    students: list[Student],
    store: StateStore,
    argument: str,
    now: datetime,
) -> CommandReply:
    parsed = split_exam_argument(argument, now.date())
    if parsed is None:
        return _single(family, "exam_ask_date")
    topic, exam_date = parsed
    for student in students:
        store.put_exam_date(
            ExamDate(student_id=student.id, competency_id=None, exam_date=exam_date)
        )
    return CommandReply(
        messages=[
            _out(family, "exam_ack", None, None, competency=topic, date=_day_month(exam_date))
        ],
        events=[_exam_event(family, topic, exam_date, now)],
    )


def _exam_event(family: Family, topic: str, exam_date: date, now: datetime) -> DomainEvent:
    return DomainEvent(
        kind=EventKind.EXAM_ANNOUNCED,
        family_id=family.id,
        idempotency_key=f"exam#{family.id}#{exam_date}",
        occurred_at=now,
        payload={"exam_date": exam_date.isoformat(), "topic": topic},
    )


def _day_month(value: date) -> str:
    return value.strftime("%d/%m")


def _schedule(family: Family, store: StateStore, argument: str) -> CommandReply:
    if not argument:
        return _single(family, "ask_schedule")
    parsed = parse_practice_time(argument)
    if parsed is None:
        return _single(family, "ask_schedule")
    hour, minute = parsed
    family.practice_time = time(hour=hour, minute=minute)
    store.put_family(family)
    return _single(family, "resumed", time=_stamp(family.practice_time))


def _forget_prompt(family: Family) -> CommandReply:
    buttons = [
        Button(label=msg("forget_yes", family.lang), callback_data=FORGET_YES),
        Button(label=msg("forget_no", family.lang), callback_data=FORGET_NO),
    ]
    return CommandReply(messages=[_out(family, "forget_confirm", buttons)])
