from dataclasses import dataclass, field
from datetime import datetime

from repaso.core.orchestration.context import Services
from repaso.schemas.channel import ChannelKind
from repaso.schemas.common import Lang
from repaso.schemas.family import Family, FamilyStatus
from repaso.schemas.student import Student
from repaso.simulator.archetypes import Archetype
from repaso.simulator.item_bank import build_item_bank

SECTION_CLUSTER = "colegio-demo-4-b"
SECTION_A = "colegio-demo-4-a"
SECTION_C = "colegio-demo-4-c"

COHORT_MIX: list[tuple[Archetype, int]] = [
    (Archetype.STEADY_MASTERY, 10),
    (Archetype.STRUGGLING, 4),
    (Archetype.DISENGAGED, 3),
    (Archetype.FAST_GUESSER, 2),
    (Archetype.COHORT_CLUSTER, 5),
    (Archetype.FORGETTING, 3),
    (Archetype.AMBIGUOUS, 2),
    (Archetype.INJECTOR, 1),
]

LOW_ABILITY = {Archetype.STRUGGLING, Archetype.COHORT_CLUSTER}


@dataclass
class CohortMember:
    family: Family
    student: Student
    archetype: Archetype


@dataclass
class CohortLedger:
    members: list[CohortMember] = field(default_factory=list)

    def by_archetype(self, archetype: Archetype) -> list[CohortMember]:
        return [member for member in self.members if member.archetype is archetype]

    @property
    def expected_struggle_students(self) -> int:
        return sum(1 for member in self.members if member.archetype in LOW_ABILITY)

    @property
    def expected_engagement_students(self) -> int:
        return len(self.by_archetype(Archetype.DISENGAGED))


    @property
    def expected_injections(self) -> int:
        return len(self.by_archetype(Archetype.INJECTOR))


def _section_for(archetype: Archetype, index: int, struggling_seen: int) -> str:
    if archetype is Archetype.COHORT_CLUSTER:
        return SECTION_CLUSTER
    if archetype is Archetype.STRUGGLING:
        return SECTION_A if struggling_seen < 2 else SECTION_C
    return SECTION_A if index % 2 == 0 else SECTION_C


def build_cohort(services: Services, now: datetime) -> CohortLedger:
    competencies = services.retriever.list_competencies(4, "math")
    for item in build_item_bank(competencies, now):
        services.store.put_item(item)

    ledger = CohortLedger()
    index = 0
    struggling_seen = 0
    for archetype, count in COHORT_MIX:
        for _ in range(count):
            index += 1
            section = _section_for(archetype, index, struggling_seen)
            if archetype is Archetype.STRUGGLING:
                struggling_seen += 1
            family = Family(
                id=f"fam{index:02d}",
                channel=ChannelKind.TELEGRAM,
                chat_ref=str(9000 + index),
                lang=Lang.ES,
                status=FamilyStatus.ACTIVE,
                invite_code="DEMO",
                created_at=now,
            )
            student = Student(
                id=f"stu{index:02d}",
                family_id=family.id,
                alias=f"Alumno{index:02d}",
                grade=4,
                section_key=section,
                created_at=now,
            )
            services.store.put_family(family)
            services.store.put_student(student)
            ledger.members.append(CohortMember(family, student, archetype))
    return ledger
