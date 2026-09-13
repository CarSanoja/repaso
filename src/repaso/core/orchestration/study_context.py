from repaso.core.harness.study_session import questions_left
from repaso.core.orchestration import turn_memory
from repaso.core.orchestration.context import Services
from repaso.i18n.competencies import competency_label
from repaso.schemas.competency import Competency
from repaso.schemas.family import Family
from repaso.schemas.item import Item
from repaso.schemas.student import Student
from repaso.schemas.study_session import StudySession
from repaso.schemas.turn import (
    ExplainContext,
    PracticeState,
    TurnContext,
    TurnDecision,
    TurnWindow,
)


def competency_of(services: Services, item: Item) -> Competency | None:
    return services.retriever.get_competency(item.competency_id)


def label_of(services: Services, family: Family, item: Item) -> str:
    competency = competency_of(services, item)
    return competency_label(competency, family.lang) if competency else ""


def read_context(
    services: Services,
    family: Family,
    student: Student,
    session: StudySession,
    item: Item,
    window: TurnWindow,
) -> TurnContext:
    return TurnContext(
        lang=family.lang,
        grade=student.grade,
        competency=label_of(services, family, item),
        practice=PracticeState.OPEN,
        question=item.stem,
        options=list(item.options),
        items_left=questions_left(session),
        answered=False,
        history=turn_memory.history_lines(services, window),
    )


def explain_context(
    services: Services,
    family: Family,
    student: Student,
    item: Item,
    decision: TurnDecision,
    said: str,
    window: TurnWindow,
) -> ExplainContext:
    competency = competency_of(services, item)
    return ExplainContext(
        lang=family.lang,
        grade=student.grade,
        competency=label_of(services, family, item),
        description=competency.description if competency else "",
        question=item.stem,
        options=list(item.options),
        asked_for=decision.asked_for,
        child_said=said,
        answered=False,
        already_tried=turn_memory.tried_approaches(window),
    )
