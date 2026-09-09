import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, time
from hashlib import sha256
from uuid import uuid4

from repaso.channel.telegram.allowlist import valid_invite
from repaso.i18n import msg
from repaso.schemas.channel import Button, ChannelKind, InboundMessage, OutboundMessage
from repaso.schemas.common import FamilyId, Lang, StudentId
from repaso.schemas.consent import ConsentRecord
from repaso.schemas.enrollment import EnrollmentProgress, EnrollmentStep
from repaso.schemas.family import Family, FamilyStatus
from repaso.schemas.student import Student
from repaso.tools.state_store import StateStore

CONSENT_VERSION = "v2"
CONSENT_YES = "consent:yes"
CONSENT_NO = "consent:no"
ALIAS_MAX_LENGTH = 20
TIME_PATTERN = re.compile(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$")


@dataclass
class EnrollmentReply:
    messages: list[OutboundMessage]
    done: bool = False


def start_enrollment(
    channel: ChannelKind, chat_ref: str, invite_code: str, lang: Lang
) -> EnrollmentProgress:
    return EnrollmentProgress(
        channel=channel,
        chat_ref=chat_ref,
        lang=lang,
        step=EnrollmentStep.CONSENT,
        invite_code=invite_code,
    )


def parse_practice_time(text: str) -> tuple[int, int] | None:
    match = TIME_PATTERN.match(text.strip().lower().replace(" ", ""))
    if match is None:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    suffix = match.group(3)
    if suffix == "pm" and hour < 12:
        hour += 12
    if suffix == "am" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    return hour, minute


def advance(
    progress: EnrollmentProgress,
    message: InboundMessage,
    store: StateStore,
    now: datetime,
    invite_codes: frozenset[str],
) -> EnrollmentReply:
    text = (message.text or "").strip()
    if progress.step is EnrollmentStep.CONSENT:
        return _consent_step(progress, message, store, text, invite_codes)
    if progress.step is EnrollmentStep.SCHEDULE:
        return _schedule_step(progress, store, text, now)
    if progress.step is EnrollmentStep.ALIAS:
        reply = _alias_step(progress, text)
    elif progress.step is EnrollmentStep.GRADE:
        reply = _grade_step(progress, text)
    elif progress.step is EnrollmentStep.SECTION:
        reply = _section_step(progress, text)
    else:
        return EnrollmentReply(messages=[])
    store.put_enrollment(progress)
    return reply


def _out(
    progress: EnrollmentProgress, key: str, buttons: list[Button] | None = None, **kwargs: object
) -> OutboundMessage:
    return OutboundMessage(
        channel=progress.channel,
        chat_ref=progress.chat_ref,
        text=msg(key, progress.lang, **kwargs),
        buttons=buttons or [],
    )


def _single(progress: EnrollmentProgress, key: str, **kwargs: object) -> EnrollmentReply:
    return EnrollmentReply(messages=[_out(progress, key, None, **kwargs)])


def _consent_step(
    progress: EnrollmentProgress,
    message: InboundMessage,
    store: StateStore,
    text: str,
    invite_codes: frozenset[str],
) -> EnrollmentReply:
    if message.callback_data == CONSENT_NO:
        store.delete_enrollment(progress.channel.value, progress.chat_ref)
        return _single(progress, "consent_declined")
    if message.callback_data == CONSENT_YES:
        progress.step = EnrollmentStep.ALIAS
        store.put_enrollment(progress)
        return _single(progress, "ask_alias")
    if not progress.invite_code and valid_invite(text, invite_codes):
        progress.invite_code = text
    store.put_enrollment(progress)
    buttons = [
        Button(label=msg("consent_accept", progress.lang), callback_data=CONSENT_YES),
        Button(label=msg("consent_decline", progress.lang), callback_data=CONSENT_NO),
    ]
    prompt = [_out(progress, "welcome"), _out(progress, "consent", buttons)]
    return EnrollmentReply(messages=prompt)


def _looks_like_real_name(alias: str) -> bool:
    if len(alias) > ALIAS_MAX_LENGTH:
        return True
    words = alias.split()
    return len(words) >= 2 and all(word[:1].isupper() for word in words)


def _alias_step(progress: EnrollmentProgress, text: str) -> EnrollmentReply:
    if not text:
        return _single(progress, "ask_alias")
    if _looks_like_real_name(text):
        return _single(progress, "alias_warning")
    progress.alias = text
    progress.step = EnrollmentStep.GRADE
    return _single(progress, "ask_grade")


def _grade_step(progress: EnrollmentProgress, text: str) -> EnrollmentReply:
    try:
        grade = int(text)
    except ValueError:
        return _single(progress, "ask_grade")
    if grade != 4:
        return _single(progress, "ask_grade")
    progress.grade = grade
    progress.step = EnrollmentStep.SECTION
    return _single(progress, "ask_section")


def _section_step(progress: EnrollmentProgress, text: str) -> EnrollmentReply:
    if not text:
        return _single(progress, "ask_section")
    progress.section_key = normalize_section(text)
    progress.step = EnrollmentStep.SCHEDULE
    return _single(progress, "ask_schedule")


def _schedule_step(
    progress: EnrollmentProgress, store: StateStore, text: str, now: datetime
) -> EnrollmentReply:
    parsed = parse_practice_time(text)
    if parsed is None:
        store.put_enrollment(progress)
        return _single(progress, "ask_schedule")
    progress.practice_hour, progress.practice_minute = parsed
    progress.step = EnrollmentStep.DONE
    return _complete(progress, store, now)


def _complete(progress: EnrollmentProgress, store: StateStore, now: datetime) -> EnrollmentReply:
    family = Family(
        id=FamilyId(uuid4().hex),
        channel=progress.channel,
        chat_ref=progress.chat_ref,
        lang=progress.lang,
        practice_time=time(hour=progress.practice_hour or 0, minute=progress.practice_minute),
        status=FamilyStatus.ACTIVE,
        invite_code=progress.invite_code,
        consent=ConsentRecord(version=CONSENT_VERSION, accepted_at=now, chat_ref=progress.chat_ref),
        created_at=now,
    )
    student = Student(
        id=StudentId(uuid4().hex),
        family_id=family.id,
        alias=progress.alias or "",
        grade=progress.grade or 1,
        section_key=progress.section_key or "",
        cohort_id=sha256(f"{progress.invite_code}:{progress.section_key}".encode()).hexdigest()[
            :24
        ],
        created_at=now,
    )
    store.put_family(family)
    store.put_student(student)
    store.delete_enrollment(progress.channel.value, progress.chat_ref)
    stamp = family.practice_time.strftime("%H:%M")
    return EnrollmentReply(
        messages=[
            _out(progress, "enrollment_done", None, alias=student.alias, time=stamp),
            _out(progress, "ask_first_material", None, alias=student.alias),
        ],
        done=True,
    )


def normalize_section(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"(\d+)(?:to|º|°|th)\b", r"\1", text)
    return "-".join(re.findall(r"[a-z0-9]+", text))
