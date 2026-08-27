from datetime import UTC, datetime

from repaso.agents.grader import grade_open, open_prompt
from repaso.config.models import ModelRole
from repaso.core.orchestration.context import TutorRun
from repaso.core.orchestration.response_graph import build_response_graph
from repaso.schemas.common import Lang
from repaso.schemas.grading import StudentResponse
from repaso.schemas.item import Item, ItemKind, ItemStatus
from repaso.schemas.provenance import Provenance, Source
from repaso.schemas.session import Capsule, PracticeSession, SessionStatus
from repaso.tools.guardrails import REDACTION, LocalScreener
from repaso.tools.llm import LocalPlaybackModel
from tests.orchestration.fixtures import FRACTIONS, make_services, seed_family

START = datetime(2026, 9, 1, 19, 0, tzinfo=UTC)
EMAIL = "ana.perez@colegio.edu.ve"
PHONE = "0412-555-1234"
ANSWER = f"la mitad, mi mama es {EMAIL} y su telefono {PHONE} por si acaso"


class RecordingJudge(LocalPlaybackModel):
    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        async for event in super().structured_output(output_model, prompt, system_prompt, **kwargs):
            yield event
        self.calls[-1]["prompt"] = str(prompt)


def open_item(store) -> Item:
    item = Item(
        id="i1",
        competency_id=FRACTIONS,
        kind=ItemKind.OPEN,
        difficulty=2,
        stem="¿Por qué 2/4 es igual a 1/2?",
        options=[],
        answer_key="1/2",
        rationale="both halves",
        rubric="2 puntos por explicar la equivalencia",
        status=ItemStatus.ACTIVE,
        provenance=Provenance(source=Source.GENERATED, created_at=START),
    )
    store.put_item(item)
    return item


def open_session(services, student_id: str) -> PracticeSession:
    session = PracticeSession(
        id="sess1",
        student_id=student_id,
        session_date=services.clock.today(),
        capsule=Capsule(concept_snippet="snippet", item_ids=["i1"]),
        status=SessionStatus.DELIVERED,
    )
    services.store.put_session(session)
    return session


def pii_response(student_id: str) -> StudentResponse:
    return StudentResponse(
        student_id=student_id, item_id="i1", text=ANSWER,
        latency_seconds=30.0, received_at=START,
    )


async def run_graph(settings, judge: RecordingJudge) -> tuple[TutorRun, object]:
    services = make_services(settings)
    services.models[ModelRole.JUDGE] = judge
    services.models[ModelRole.STRUCTURED].enqueue({"action": "continue", "reason": "ok"})
    family, student = seed_family(services.store)
    item = open_item(services.store)
    session = open_session(services, student.id)
    run = TutorRun(
        family=family, student=student, session=session, items=[item],
        response=pii_response(student.id),
    )
    await build_response_graph(services, run).invoke_async("response")
    return run, services


def graded(judge_reply: dict):
    return RecordingJudge([judge_reply])


async def test_the_judge_prompt_never_sees_the_email_or_the_phone(settings):
    judge = graded({"correct": True, "rubric_points": 2.0, "confidence": 0.9, "feedback": "Bien."})
    await run_graph(settings, judge)

    sent = str(judge.calls)
    assert EMAIL not in sent
    assert PHONE not in sent
    assert REDACTION in judge.calls[0]["prompt"]
    assert "la mitad" in judge.calls[0]["prompt"]


async def test_the_stored_grade_evidence_keeps_the_answer_verbatim(settings):
    judge = graded({"correct": True, "rubric_points": 2.0, "confidence": 0.9, "feedback": "Bien."})
    run, services = await run_graph(settings, judge)

    assert run.grade.evidence.quote == ANSWER
    assert EMAIL in run.grade.evidence.quote
    assert PHONE in run.grade.evidence.quote
    stored = services.grade_log.by_student(run.student.id)
    assert stored and stored[-1].evidence.quote == ANSWER


async def test_a_quarantined_answer_keeps_the_verbatim_text_for_the_parent(settings):
    judge = graded({"correct": True, "rubric_points": 1.0, "confidence": 0.2, "feedback": ""})
    run, _ = await run_graph(settings, judge)

    assert run.quarantine is not None
    assert run.quarantine.payload["answer"] == ANSWER
    assert run.quarantine.evidence.quote == ANSWER
    assert EMAIL not in str(judge.calls)


async def test_grade_open_without_llm_text_sends_the_verbatim_answer():
    judge = graded({"correct": True, "rubric_points": 2.0, "confidence": 0.9, "feedback": "Bien."})
    item = Item(
        id="i1", competency_id=FRACTIONS, kind=ItemKind.OPEN, difficulty=2,
        stem="stem", options=[], answer_key="1/2", rationale="r",
        rubric="2 puntos", status=ItemStatus.ACTIVE,
        provenance=Provenance(source=Source.GENERATED, created_at=START),
    )
    await grade_open(
        item=item, response=pii_response("s1"), lang=Lang.ES, model=judge,
        confidence_threshold=0.7, graded_at=START, family_id="f1",
    )
    assert EMAIL in judge.calls[0]["prompt"]


def test_open_prompt_carries_whatever_answer_text_it_is_given():
    item = Item(
        id="i1", competency_id=FRACTIONS, kind=ItemKind.OPEN, difficulty=2,
        stem="stem", options=[], answer_key="1/2", rationale="r",
        rubric=None, status=ItemStatus.ACTIVE,
        provenance=Provenance(source=Source.GENERATED, created_at=START),
    )
    redacted = LocalScreener().redact(ANSWER)
    prompt = open_prompt(item, redacted, Lang.ES)
    assert redacted in prompt
    assert EMAIL not in prompt
    assert PHONE not in prompt
