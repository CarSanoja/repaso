from datetime import datetime
from enum import StrEnum
from typing import Annotated

from repaso.schemas.common import (
    FrozenStrictModel,
    ItemId,
    Lang,
    SessionId,
    StrictBaseModel,
)
from repaso.schemas.nullable import NULL_IS_BLANK, NULL_IS_EMPTY


class TurnIntent(StrEnum):
    DISTRESS = "distress"
    ANSWER = "answer"
    EXPLANATION = "explanation"
    ANOTHER_QUESTION = "another_question"
    STOP = "stop"
    ABOUT_THE_PRACTICE = "about_the_practice"
    SOMETHING_ELSE = "something_else"


class Speaker(StrEnum):
    CHILD = "child"
    ADULT = "adult"
    UNCLEAR = "unclear"


class PracticeState(StrEnum):
    NOT_SENT = "not_sent"
    OPEN = "open"
    FINISHED = "finished"


class TurnDecision(StrictBaseModel):
    intent: TurnIntent
    speaker: Speaker
    asked_for: Annotated[str, NULL_IS_BLANK] = ""
    answer_text: Annotated[str, NULL_IS_BLANK] = ""


class TurnContext(FrozenStrictModel):
    lang: Lang
    grade: int
    competency: str
    practice: PracticeState
    question: str = ""
    options: Annotated[list[str], NULL_IS_EMPTY] = []
    items_left: int = 0
    answered: bool = False
    history: Annotated[list[str], NULL_IS_EMPTY] = []


class TurnNote(FrozenStrictModel):
    turn_id: str
    intent: TurnIntent
    at: datetime
    item_id: ItemId | None = None
    item_index: int = 0
    said: str = ""
    correct: bool | None = None
    explained: str = ""


class TurnWindow(StrictBaseModel):
    session_id: SessionId
    notes: list[TurnNote] = []


class ExplainContext(FrozenStrictModel):
    lang: Lang
    grade: int
    competency: str
    question: str
    description: str = ""
    options: Annotated[list[str], NULL_IS_EMPTY] = []
    asked_for: str = ""
    answer_given: str = ""
    child_said: str = ""
    answered: bool = False
    was_correct: bool | None = None
    answer_key: str = ""
    rationale: str = ""
    already_tried: Annotated[list[str], NULL_IS_EMPTY] = []


class Explanation(StrictBaseModel):
    text: str
    approach: Annotated[str, NULL_IS_BLANK] = ""
