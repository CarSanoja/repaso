from repaso.core.bank.query import BankQuery, query_bank, seen_recently
from repaso.core.bank.sources import bank_items
from repaso.core.orchestration.context import Services
from repaso.schemas.family import Family
from repaso.schemas.item import Item, ItemKind
from repaso.schemas.student import Student
from repaso.schemas.study_session import StudyGoal, StudySession

STUDY_KINDS = (ItemKind.MCQ,)


def already_practised(services: Services, student: Student) -> frozenset[str]:
    today = services.clock.today()
    seen = set(seen_recently(services.store.list_spaced(student.id), today))
    capsule = services.store.get_session_by_date(student.id, today)
    if capsule is not None and capsule.capsule is not None:
        seen.update(capsule.capsule.item_ids)
    return frozenset(seen)


def available_items(
    services: Services,
    family: Family,
    student: Student,
    goal: StudyGoal,
    limit: int,
    session: StudySession | None = None,
) -> list[Item]:
    exclude = set(already_practised(services, student))
    if session is not None:
        exclude.update(session.progress.served)
    return query_bank(
        bank_items(services, family, student.grade),
        BankQuery(
            competency_ids=(goal.competency_id,) if goal.competency_id else (),
            kinds=STUDY_KINDS,
            bloom=goal.bloom,
            lang=family.lang,
            grade=student.grade,
            exclude=frozenset(exclude),
            limit=limit,
        ),
    )
