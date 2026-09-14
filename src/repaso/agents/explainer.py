import json

from repaso.agents.base import StructuredCallFailed, structured
from repaso.agents.prompts.explainer import PROMPT_VERSION, SYSTEM
from repaso.schemas.turn import ExplainContext, Explanation


def explain_prompt(context: ExplainContext) -> str:
    # Author instructions belong in SYSTEM. The guarded user message contains
    # only lesson data, including every untrusted field supplied by the family.
    hidden = {"answer_key", "rationale", "answer_given", "was_correct", "options"}
    data = context.model_dump(mode="json", exclude=hidden if not context.answered else set())
    return json.dumps(data, ensure_ascii=False, indent=2)


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
