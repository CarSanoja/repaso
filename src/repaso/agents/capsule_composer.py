from hashlib import sha256

from pydantic import BaseModel

from repaso.agents.base import StructuredCallFailed, structured
from repaso.agents.prompts.capsule_composer import PROMPT_VERSION, SYSTEM
from repaso.i18n import msg
from repaso.i18n.competencies import competency_label
from repaso.schemas.channel import Button, ChannelKind, OutboundMessage
from repaso.schemas.common import Lang
from repaso.schemas.competency import Competency
from repaso.schemas.item import Item, ItemKind
from repaso.schemas.session import Capsule, PracticeSession


class Snippet(BaseModel):
    text: str


def render_item(item: Item) -> str:
    if item.kind is not ItemKind.MCQ or not item.options:
        return item.stem
    options = [f"{number}. {option}" for number, option in enumerate(item.options, start=1)]
    return "\n".join([item.stem, *options])


def item_buttons(session_id: str, item: Item) -> list[Button]:
    if item.kind is not ItemKind.MCQ:
        return []
    return [
        Button(label=option, callback_data=f"ans:{answer_ref(session_id, item.id)}:{number}")
        for number, option in enumerate(item.options, start=1)
    ]


def answer_ref(session_id: str, item_id: str) -> str:
    return sha256(f"{session_id}:{item_id}".encode()).hexdigest()[:24]


async def compose_capsule(
    session: PracticeSession,
    items: list[Item],
    competency: Competency,
    alias: str,
    lang: Lang,
    model,
) -> tuple[Capsule, OutboundMessage]:
    snippet = await _snippet(competency, lang, model)
    capsule = Capsule(concept_snippet=snippet, item_ids=[item.id for item in items])
    parts = [
        msg("capsule_header", lang, alias=alias, competency=competency_label(competency, lang)),
        snippet,
    ]
    first = items[0] if items else None
    if first is not None:
        parts.append(render_item(first))
    message = OutboundMessage(
        channel=ChannelKind.TELEGRAM,
        chat_ref="",
        text="\n\n".join(parts),
        buttons=item_buttons(session.id, first) if first is not None else [],
    )
    return capsule, message


async def _snippet(competency: Competency, lang: Lang, model) -> str:
    fallback = (
        f"Hoy practicamos {competency_label(competency, lang)}. Lee cada pregunta con calma."
        if lang is Lang.ES
        else competency.description
    )
    text = (
        f"Language code: {lang.value}\n"
        f"Subject: {competency.subject}\n"
        f"School grade: {competency.grade}\n"
        f"Competency: {competency.name}\n"
        f"What it covers: {competency.description}\n"
        f"Write the reminder in {lang.value}."
    )
    try:
        result = await structured(model, Snippet, SYSTEM, text, PROMPT_VERSION)
    except StructuredCallFailed:
        return fallback
    return result.text.strip() or fallback
