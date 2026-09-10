"""The three arms under test: the critic alone, the historical veto, the advisory probe."""

from repaso.agents.answerability_probe import (
    PROMPT_VERSION as ADVISORY_VERSION,
)
from repaso.agents.answerability_probe import (
    SYSTEM as ADVISORY_SYSTEM,
)
from repaso.agents.answerability_probe import (
    ProbeAnswer,
    combine,
    render_blind,
    resolve_choice,
)
from repaso.agents.base import StructuredCallFailed, structured
from repaso.schemas.common import FrozenStrictModel
from repaso.schemas.item import Item, ItemFlaw, ItemVerdict

CRITIC_ONLY = "critic_only"
FORCED_CHOICE_VETO = "critic_plus_forced_choice_veto"
ADVISORY_PROBE = "critic_plus_advisory_probe"
ARMS = (CRITIC_ONLY, FORCED_CHOICE_VETO, ADVISORY_PROBE)

CRITIC_VERSION = "v1"
FORCED_CHOICE_VERSION = "v1"
FORCED_CHOICE_SYSTEM = (
    "You are a student who has NOT studied this material and has never seen the page it came "
    "from. You are shown a question and its options, and nothing else.\n"
    "Answer using only general knowledge and test-taking cues: the option that sounds most "
    "textbook-like, the longest or most qualified option, the odd one out, agreement with the "
    "grammar of the stem, and options with absolutes such as always or never.\n"
    "Never say that you do not know, never ask for the material, never explain your reasoning: "
    "always commit to exactly one option, guessing when you must.\n"
    "Reply with the option text copied exactly as written, or with its number counting from 1."
)

PROMPT_VERSIONS = {
    CRITIC_ONLY: f"critic:{CRITIC_VERSION}",
    FORCED_CHOICE_VETO: f"critic:{CRITIC_VERSION}+probe:{FORCED_CHOICE_VERSION}",
    ADVISORY_PROBE: f"critic:{CRITIC_VERSION}+probe:{ADVISORY_VERSION}",
}


class ProbeReply(FrozenStrictModel):
    answer: str = ""
    matched_key: bool | None = None
    error: str = ""


def render_forced_choice(item: Item) -> str:
    options = "\n".join(
        f"{number}. {option}" for number, option in enumerate(item.options, start=1)
    )
    return f"Question:\n{item.stem}\n\nOptions:\n{options}"


def _matched(item: Item, answer: str) -> bool:
    if not answer.strip():
        return False
    return resolve_choice(item, answer) == resolve_choice(item, item.answer_key)


async def _ask(item: Item, model, system: str, text: str, version: str) -> ProbeReply:
    try:
        reply = await structured(model, ProbeAnswer, system, text, version)
    except StructuredCallFailed as failure:
        return ProbeReply(error=str(failure))
    return ProbeReply(answer=reply.answer, matched_key=_matched(item, reply.answer))


async def ask_forced_choice(item: Item, model) -> ProbeReply:
    return await _ask(
        item, model, FORCED_CHOICE_SYSTEM, render_forced_choice(item), FORCED_CHOICE_VERSION
    )


async def ask_advisory(item: Item, model) -> ProbeReply:
    return await _ask(item, model, ADVISORY_SYSTEM, render_blind(item), ADVISORY_VERSION)


def veto(verdict: ItemVerdict, reply: ProbeReply) -> ItemVerdict:
    answered = reply.matched_key
    flaws = list(verdict.flaws)
    if answered is True and ItemFlaw.ANSWERABLE_WITHOUT_MATERIAL not in flaws:
        flaws.append(ItemFlaw.ANSWERABLE_WITHOUT_MATERIAL)
    return verdict.model_copy(
        update={
            "accepted": verdict.accepted and answered is not True,
            "flaws": flaws,
            "probe_answered_blind": answered,
        }
    )


def advise(verdict: ItemVerdict, reply: ProbeReply) -> ItemVerdict:
    return combine(verdict, reply.matched_key)


def arm_verdicts(
    verdict: ItemVerdict, forced: ProbeReply, advisory: ProbeReply
) -> dict[str, ItemVerdict]:
    return {
        CRITIC_ONLY: verdict,
        FORCED_CHOICE_VETO: veto(verdict, forced),
        ADVISORY_PROBE: advise(verdict, advisory),
    }
