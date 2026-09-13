from dataclasses import dataclass

from repaso.agents.capsule_composer import item_buttons, render_item
from repaso.agents.explainer import explain
from repaso.config.models import ModelRole
from repaso.core.orchestration import turn_memory
from repaso.core.orchestration.context import ChannelRun, Route, Services
from repaso.i18n import msg
from repaso.i18n.competencies import competency_label
from repaso.schemas.channel import Button, OutboundMessage
from repaso.schemas.competency import Competency
from repaso.schemas.family import Family
from repaso.schemas.item import Item
from repaso.schemas.session import PracticeSession
from repaso.schemas.student import Student
from repaso.schemas.turn import (
    ExplainContext,
    PracticeState,
    TurnDecision,
    TurnIntent,
    TurnWindow,
)

EXPLAIN_ROLE = ModelRole.GENERATE
TIME_FORMAT = "%H:%M"
CLOSED_KEYS = {
    PracticeState.FINISHED: "turn_practice_done",
    PracticeState.NOT_SENT: "turn_practice_not_sent",
}
INTENT_KEYS = {
    TurnIntent.STOP: "turn_stop",
    TurnIntent.ABOUT_THE_PRACTICE: "turn_about_practice",
    TurnIntent.SOMETHING_ELSE: "turn_off_task",
}


@dataclass
class TurnTarget:
    turn_id: str
    state: PracticeState
    window: TurnWindow
    student: Student | None = None
    session: PracticeSession | None = None
    item: Item | None = None
    item_index: int = 0
    answered: bool = False
    competency: Competency | None = None


def say(run: ChannelRun, family: Family, text: str, buttons: list[Button] | None = None) -> None:
    run.outbound.append(
        OutboundMessage(
            channel=family.channel,
            chat_ref=family.chat_ref,
            text=text,
            buttons=buttons or [],
        )
    )


def speak(run: ChannelRun, family: Family, key: str) -> None:
    say(run, family, msg(key, family.lang, time=family.practice_time.strftime(TIME_FORMAT)))


def reply_key(intent: TurnIntent, state: PracticeState) -> str:
    if intent in INTENT_KEYS:
        return INTENT_KEYS[intent]
    if intent is TurnIntent.ANOTHER_QUESTION and state is PracticeState.FINISHED:
        return "turn_more_tomorrow"
    return CLOSED_KEYS.get(state, "turn_practice_not_sent")


def topic(target: TurnTarget, family: Family) -> str:
    if target.competency is None:
        return ""
    return competency_label(target.competency, family.lang)


def explain_context(family: Family, target: TurnTarget, decision: TurnDecision, said: str):
    answer = turn_memory.last_answer(target.window, target.item.id)
    return ExplainContext(
        lang=family.lang,
        grade=target.student.grade if target.student else 0,
        competency=topic(target, family),
        description=target.competency.description if target.competency else "",
        question=target.item.stem,
        options=list(target.item.options),
        asked_for=decision.asked_for,
        answer_given=answer.said if answer else "",
        child_said=said,
        answered=target.answered,
        was_correct=answer.correct if answer else None,
        answer_key=target.item.answer_key if target.answered else "",
        rationale=target.item.rationale if target.answered else "",
        already_tried=turn_memory.tried_approaches(target.window),
    )


async def explain_turn(
    services: Services, run: ChannelRun, family: Family, target: TurnTarget, decision, said: str
) -> str:
    explanation = await explain(
        explain_context(family, target, decision, said), services.model(EXPLAIN_ROLE)
    )
    if explanation is not None:
        say(run, family, explanation.text)
        return explanation.approach
    if target.answered:
        say(run, family, target.item.rationale)
    else:
        speak(run, family, "turn_explain_unavailable")
    return ""


async def reply_to(
    services: Services,
    run: ChannelRun,
    family: Family,
    target: TurnTarget,
    decision: TurnDecision,
    said: str,
) -> None:
    run.route = Route.CONVERSATION
    explained = ""
    if decision.intent is TurnIntent.EXPLANATION and target.item is not None:
        explained = await explain_turn(services, run, family, target, decision, said)
    elif decision.intent is TurnIntent.ANOTHER_QUESTION and target.state is PracticeState.OPEN:
        say(run, family, render_item(target.item), item_buttons(target.session.id, target.item))
    else:
        speak(run, family, reply_key(decision.intent, target.state))
    remember_turn(services, family, target, decision, said, explained)


def remember_turn(
    services: Services,
    family: Family,
    target: TurnTarget,
    decision: TurnDecision,
    said: str,
    explained: str,
) -> None:
    if target.session is None:
        return
    turn_memory.remember(
        services,
        family.id,
        target.session.id,
        turn_memory.note(
            turn_id=target.turn_id,
            intent=decision.intent,
            at=services.clock.now(),
            item=target.item,
            item_index=target.item_index,
            said=said,
            explained=explained,
        ),
    )
