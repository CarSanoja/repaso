"""An explicitly synthetic rehearsal running the application's actual learning paths."""

import asyncio
from datetime import UTC, datetime

from repaso.config.models import ModelRole
from repaso.core.harness.clock import SimClock
from repaso.core.orchestration.outbox import deliver
from repaso.core.orchestration.runner import resolve_escalation, start_daily_session
from repaso.core.orchestration.study_channel import handle_study_text
from repaso.core.orchestration.study_flow import start_sitting
from repaso.core.telemetry.context import invocation_context
from repaso.runtime.context import build_runtime_services
from repaso.schemas.channel import ChannelKind
from repaso.schemas.escalation import Escalation, EscalationKind, EscalationOption
from repaso.schemas.family import Family, FamilyStatus
from repaso.schemas.item import BloomLevel, Item, ItemKind, ItemStatus
from repaso.schemas.provenance import Provenance, Source
from repaso.schemas.student import Student

FAMILY_ID = "memory-demo-family"
COMPETENCY = "math.g4.fractions.equivalence"


class MemoryRehearsal:
    def __init__(self, settings):
        if not settings.local_mode:
            raise ValueError("rehearsal requires local mode")
        self.services = build_runtime_services(settings)
        self.clock = SimClock(datetime.now(UTC))
        self.services.clock = self.clock
        self.family = Family(
            id=FAMILY_ID,
            channel=ChannelKind.TELEGRAM,
            chat_ref="100",
            invite_code="SYNTHETIC",
            status=FamilyStatus.ACTIVE,
            created_at=self.clock.now(),
        )
        self.student = Student(
            id="memory-demo-student",
            family_id=FAMILY_ID,
            alias="Sofi (demo)",
            grade=4,
            section_key="Community demo",
            created_at=self.clock.now(),
        )
        self.completed = {}
        self.lock = asyncio.Lock()

    async def prepare(self):
        s = self.services
        s.store.put_family(self.family)
        s.store.put_student(self.student)
        for i in range(12):
            s.store.put_item(
                Item(
                    id=f"memory-item-{i:02}",
                    family_id=FAMILY_ID,
                    competency_id=COMPETENCY,
                    kind=ItemKind.MCQ,
                    difficulty=2,
                    bloom=BloomLevel.REMEMBER,
                    grade=4,
                    stem=f"¿Cuál fracción equivale a 1/2? · Ejercicio {i + 1}",
                    options=["2/4", "1/3", "3/4"],
                    answer_key="2/4",
                    rationale="Multiplicas el numerador y el denominador por dos.",
                    status=ItemStatus.ACTIVE,
                    provenance=Provenance(source=Source.GENERATED, created_at=self.clock.now()),
                )
            )
        s.store.put_escalation(
            Escalation(
                id="memory-demo-decision",
                kind=EscalationKind.STRUGGLE_TRIAGE,
                family_id=FAMILY_ID,
                student_id=self.student.id,
                competency_id=COMPETENCY,
                summary="Prepared demo decision: choose lighter practice for seven days.",
                options=[
                    EscalationOption(
                        key="reduce_load", label="Less practice", tradeoff="One question"
                    )
                ],
                created_at=self.clock.now(),
            )
        )
        token = invocation_context.set(
            {"family_id": FAMILY_ID, "correlation_id": "rehearsal-setup"}
        )
        try:
            s.models[ModelRole.GENERATE].enqueue(
                {"text": "Hoy practicamos fracciones equivalentes."}
            )
            await start_daily_session(s, self.family, self.student)
            reply = start_sitting(s, self.family, self.student, "fracciones equivalentes")
            deliver(s, reply.messages, "rehearsal-start", FAMILY_ID)
        finally:
            invocation_context.reset(token)

    async def step(self, step: str) -> dict:
        async with self.lock:
            if step in self.completed:
                return self.completed[step]
            order = ["help", "another", "answer", "reduce"]
            if any(prior not in self.completed for prior in order[: order.index(step)]):
                raise ValueError("Complete the rehearsal steps in order.")
            token = invocation_context.set(
                {"family_id": FAMILY_ID, "correlation_id": f"rehearsal-{step}"}
            )
            try:
                result = await self._step(step)
                self.completed[step] = result
                return result
            finally:
                invocation_context.reset(token)

    async def _step(self, step):
        s = self.services
        self.clock.advance(minutes=1)
        if step in {"help", "another"}:
            s.models[ModelRole.STRUCTURED].enqueue(
                {
                    "intent": "explanation",
                    "speaker": "child",
                    "asked_for": "another explanation",
                }
            )
            s.models[ModelRole.GENERATE].enqueue(
                {
                    "text": "Divide una barra en cuatro y pinta dos."
                    if step == "help"
                    else "Imagina media pizza: la misma cantidad, escrita con partes más pequeñas.",
                    "approach": "bar split into quarters" if step == "help" else "pizza halves",
                }
            )
            text = "no entiendo" if step == "help" else "sigo sin entender, de otra forma"
            reply = await handle_study_text(s, self.family, text, 8.0, f"demo-{step}")
            deliver(s, reply.messages, f"rehearsal-{step}", FAMILY_ID)
            return {"messages": [m.text for m in reply.messages]}
        if step == "answer":
            reply = await handle_study_text(s, self.family, "1", 12.0, "demo-answer")
            deliver(s, reply.messages, "rehearsal-answer", FAMILY_ID)
            return {"messages": [m.text for m in reply.messages]}
        decision = s.store.get_escalation("memory-demo-decision")
        result = resolve_escalation(s, self.family, decision, "reduce_load")
        self.clock.advance(days=1)
        s.models[ModelRole.GENERATE].enqueue({"text": "Hoy hacemos una pregunta con calma."})
        next_day = await start_daily_session(s, self.family, self.student)
        return {
            "messages": ["SIMULATED CLOCK: advanced to the next day."]
            + [m.text for m in result.outbound + next_day.outbound]
        }
