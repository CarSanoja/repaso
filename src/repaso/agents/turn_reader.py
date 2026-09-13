from repaso.agents.base import StructuredCallFailed, structured
from repaso.agents.intake_screener import frame_untrusted
from repaso.agents.prompts.turn_reader import (
    HISTORY_HEADER,
    PROMPT_VERSION,
    REQUEST,
    STATE_ANSWERED,
    STATE_FINISHED,
    STATE_NOT_SENT,
    STATE_OPEN,
    STATE_WAITING,
    SYSTEM,
)
from repaso.schemas.turn import PracticeState, TurnContext, TurnDecision


def numbered(question: str, options: list[str]) -> str:
    if not options:
        return question
    lines = [f"{number}. {option}" for number, option in enumerate(options, start=1)]
    return "\n".join([question, *lines])


def state_block(context: TurnContext) -> str:
    question = numbered(context.question, context.options)
    if context.practice is PracticeState.NOT_SENT or not question:
        return STATE_NOT_SENT
    if context.practice is PracticeState.FINISHED:
        return STATE_FINISHED.format(question=question)
    seen = STATE_ANSWERED if context.answered else STATE_WAITING
    open_state = STATE_OPEN.format(question=question, items_left=context.items_left)
    return f"{open_state}\n{seen}"


def history_block(context: TurnContext) -> str:
    if not context.history:
        return ""
    return HISTORY_HEADER.format(lines="\n".join(context.history))


def read_prompt(context: TurnContext, text: str) -> str:
    return REQUEST.format(
        lang=context.lang.value,
        grade=context.grade,
        competency=context.competency,
        state=state_block(context),
        history=history_block(context),
        message=frame_untrusted(text),
    )


async def read_turn(text: str, context: TurnContext, model) -> TurnDecision | None:
    try:
        return await structured(
            model,
            TurnDecision,
            SYSTEM.format(lang=context.lang.value),
            read_prompt(context, text),
            PROMPT_VERSION,
        )
    except StructuredCallFailed:
        return None
