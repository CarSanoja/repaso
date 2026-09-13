from repaso.agents.turn_reader import read_turn
from repaso.schemas.common import Lang
from repaso.schemas.turn import PracticeState, TurnContext, TurnIntent
from tests.distress_corpus import (
    DISTRESS_LINES,
    FIGURE_LINES,
    FOREIGN_LINES,
    ORDINARY_LINES,
    PRACTICE_LINES,
    SPELLED_LINES,
)

CONTEXT = TurnContext(
    lang=Lang.ES,
    grade=4,
    competency="Fracciones equivalentes",
    practice=PracticeState.OPEN,
    question="¿Qué fracción equivale a 1/2?",
    options=["2/4", "1/3", "3/5"],
    items_left=2,
)

DISTRESS = TurnIntent.DISTRESS.value
PARENT_CALLED = "parent_called"
GUARDRAIL_REPLY = "guardrail_reply"
CARRIED_ON = "carried_on"


def reaching_rows() -> list[dict]:
    rows = [{"tag": "measured", "text": text} for text in DISTRESS_LINES]
    rows += [{"tag": "spelled", "text": text} for text in SPELLED_LINES]
    rows += [{"tag": tag, "text": text} for tag, text in FOREIGN_LINES]
    return [row | {"expected": DISTRESS, "should_reach": True} for row in rows]


def quiet_rows() -> list[dict]:
    rows = [{"tag": "figure", "text": text, "expected": ""} for text in FIGURE_LINES]
    rows += [{"tag": "bad_evening", "text": text, "expected": ""} for text in ORDINARY_LINES]
    rows += [
        {"tag": "practice", "text": text, "expected": intent.value}
        for text, intent in PRACTICE_LINES
    ]
    return [row | {"should_reach": False} for row in rows]


def outcome(blocked: bool, intents: list[str]) -> str:
    if blocked:
        return GUARDRAIL_REPLY
    if DISTRESS in intents:
        return PARENT_CALLED
    return CARRIED_ON


async def walk(screener, model, rows: list[dict], samples: int) -> list[dict]:
    walked = []
    for row in rows:
        verdict = screener.screen(row["text"])
        intents = []
        for _ in range(samples):
            decision = await read_turn(row["text"], CONTEXT, model)
            intents.append("unread" if decision is None else decision.intent.value)
        walked.append(
            row
            | {
                "guardrail_blocked": not verdict.safe,
                "guardrail_reasons": verdict.reasons,
                "guardrail_offered_reply": bool(verdict.reply),
                "read_as": intents,
                "met": sum(1 for intent in intents if intent == row["expected"]),
                "alarms": intents.count(DISTRESS),
                "samples": samples,
                "outcome": outcome(not verdict.safe, intents),
            }
        )
    return walked
