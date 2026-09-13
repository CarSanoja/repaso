from repaso.agents.base import StructuredCallFailed, structured
from repaso.agents.intake_screener import frame_untrusted
from repaso.agents.prompts.explainer import (
    ANSWER_LINE,
    PROMPT_VERSION,
    REQUEST,
    SAID_LINE,
    STATUS_ANSWERED,
    STATUS_RIGHT,
    STATUS_WAITING,
    STATUS_WRONG,
    SYSTEM,
    TRIED_HEADER,
)
from repaso.agents.turn_reader import numbered
from repaso.schemas.turn import ExplainContext, Explanation


def status_block(context: ExplainContext) -> str:
    if not context.answered:
        return STATUS_WAITING
    if context.was_correct is None:
        template = STATUS_ANSWERED
    else:
        template = STATUS_RIGHT if context.was_correct else STATUS_WRONG
    return template.format(answer_key=context.answer_key, rationale=context.rationale)


def tried_block(context: ExplainContext) -> str:
    if not context.already_tried:
        return ""
    lines = "\n".join(f"- {approach}" for approach in context.already_tried)
    return TRIED_HEADER.format(lines=lines)


def family_block(context: ExplainContext) -> str:
    lines = []
    if context.answer_given:
        lines.append(ANSWER_LINE.format(answer=context.answer_given))
    if context.child_said:
        lines.append(SAID_LINE.format(said=context.child_said))
    return frame_untrusted("\n".join(lines))


def explain_prompt(context: ExplainContext) -> str:
    return REQUEST.format(
        lang=context.lang.value,
        grade=context.grade,
        competency=context.competency,
        description=context.description,
        question=numbered(context.question, context.options),
        status=status_block(context),
        tried=tried_block(context),
        asked_for=context.asked_for,
        message=family_block(context),
    )


async def explain(context: ExplainContext, model) -> Explanation | None:
    try:
        reply = await structured(
            model,
            Explanation,
            SYSTEM.format(grade=context.grade, lang=context.lang.value),
            explain_prompt(context),
            PROMPT_VERSION,
        )
    except StructuredCallFailed:
        return None
    return reply if reply.text.strip() else None
