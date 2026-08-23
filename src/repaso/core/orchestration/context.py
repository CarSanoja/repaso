from dataclasses import dataclass, field
from typing import Any

from repaso.config.models import ModelRole
from repaso.config.settings import Settings
from repaso.core.harness.clock import Clock
from repaso.schemas.channel import OutboundMessage
from repaso.schemas.competency import Competency, CompetencyMatch
from repaso.schemas.escalation import Escalation
from repaso.schemas.family import Family
from repaso.schemas.grading import GradeResult, StudentResponse
from repaso.schemas.item import Item, ItemVerdict
from repaso.schemas.material import Material
from repaso.schemas.review import QuarantineItem
from repaso.schemas.session import PracticeSession
from repaso.schemas.student import Student
from repaso.schemas.verification import DailyCloseReport
from repaso.tools.event_bus import EventPublisher
from repaso.tools.guardrails import Screener, ScreenVerdict
from repaso.tools.knowledge import KnowledgeRetriever
from repaso.tools.media_store import MediaStore
from repaso.tools.ocr import TextExtractor
from repaso.tools.state_store import StateStore
from repaso.tools.telegram import ChannelSender


@dataclass
class Services:
    settings: Settings
    clock: Clock
    store: StateStore
    grade_log: Any
    media: MediaStore
    extractor: TextExtractor
    screener: Screener
    retriever: KnowledgeRetriever
    publisher: EventPublisher
    sender: ChannelSender
    models: dict[ModelRole, Any]

    def model(self, role: ModelRole) -> Any:
        return self.models[role]


@dataclass
class IngestRun:
    family: Family
    student: Student
    material: Material
    data: bytes
    screen: ScreenVerdict | None = None
    matches: list[CompetencyMatch] = field(default_factory=list)
    competency: Competency | None = None
    generated: list[Item] = field(default_factory=list)
    verdicts: list[ItemVerdict] = field(default_factory=list)
    kept: list[Item] = field(default_factory=list)
    outbound: list[OutboundMessage] = field(default_factory=list)
    terminal: str | None = None


@dataclass
class TutorRun:
    family: Family
    student: Student
    session: PracticeSession | None = None
    items: list[Item] = field(default_factory=list)
    competency: Competency | None = None
    response: StudentResponse | None = None
    grade: GradeResult | None = None
    quarantine: QuarantineItem | None = None
    decision_action: str | None = None
    escalations: list[Escalation] = field(default_factory=list)
    outbound: list[OutboundMessage] = field(default_factory=list)
    terminal: str | None = None


@dataclass
class CloseRun:
    report: DailyCloseReport | None = None
    cohort_fired: list[str] = field(default_factory=list)
    retired_items: list[str] = field(default_factory=list)
    outbound: list[OutboundMessage] = field(default_factory=list)
