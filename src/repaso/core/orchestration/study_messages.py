from repaso.agents.capsule_composer import render_item
from repaso.i18n import msg
from repaso.schemas.channel import Button, OutboundMessage
from repaso.schemas.family import Family
from repaso.schemas.item import Item, ItemKind
from repaso.schemas.study_session import CloseReason, StudySession

STUDY_PREFIX = "sit:"
CLOSING_KEYS: dict[CloseReason, str] = {
    CloseReason.QUESTIONS_SPENT: "study_done",
    CloseReason.MINUTES_SPENT: "study_done_time",
    CloseReason.DAY_SPENT: "study_done_day",
    CloseReason.ENOUGH_FOR_TODAY: "study_done_enough",
    CloseReason.BANK_EMPTY: "study_done_bank",
    CloseReason.FAMILY_CLOSED: "study_done",
    CloseReason.EXPIRED: "study_done",
}


def say(family: Family, key: str, buttons: list[Button] | None = None, **kwargs) -> OutboundMessage:
    return OutboundMessage(
        channel=family.channel,
        chat_ref=family.chat_ref,
        text=msg(key, family.lang, **kwargs),
        buttons=buttons or [],
    )


def study_ref(session_id: str, item_id: str, number: int) -> str:
    return f"{STUDY_PREFIX}{session_id}:{item_id}:{number}"


def study_buttons(session_id: str, item: Item) -> list[Button]:
    if item.kind is not ItemKind.MCQ:
        return []
    return [
        Button(label=option, callback_data=study_ref(session_id, item.id, number))
        for number, option in enumerate(item.options, start=1)
    ]


def question(family: Family, session: StudySession, item: Item, asked: int) -> OutboundMessage:
    header = msg("study_question", family.lang, asked=asked, total=session.budget.questions)
    return OutboundMessage(
        channel=family.channel,
        chat_ref=family.chat_ref,
        text=f"{header}\n\n{render_item(item)}",
        buttons=study_buttons(session.id, item),
    )


def closing(family: Family, session: StudySession, reason: CloseReason) -> OutboundMessage:
    progress = session.progress
    return say(
        family,
        CLOSING_KEYS[reason],
        correct=progress.correct,
        answered=progress.correct + progress.wrong,
        minutes=session.budget.minutes,
    )
