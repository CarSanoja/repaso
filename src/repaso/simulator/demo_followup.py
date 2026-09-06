"""Authored continuation; real harness transitions, synthetic model outputs."""

from dataclasses import asdict

from repaso.agents.capsule_composer import item_buttons
from repaso.config.models import ModelRole
from repaso.core.orchestration.runner import active_session, current_item
from repaso.schemas.item import ItemKind
from repaso.simulator.demo_stage import session_event
from repaso.simulator.demo_transcript import CHILD, PARENT
from repaso.tools.grade_log import effective_grades
from repaso.tools.instrumented_model import instrument_models
from repaso.tools.llm import LocalPlaybackModel

COMPETENCY = "math.g4.fractions.equivalence"
NOTE = (
    "Nota para la maestra: en esta práctica de ejemplo, Sofi sigue sumando el mismo número "
    "al numerador y al denominador. Hubo nueve respuestas revisadas y la dificultad persiste. "
    "¿Podemos repasar equivalencia con dos dibujos de la misma cantidad? "
    "Esta nota describe la práctica; no es un diagnóstico."
)
SNIPPET = {"text": "Multiplica o divide arriba y abajo por el mismo número: el tamaño no cambia."}


def checkpoint(stage, family, student, title):
    services = stage.services
    grades = effective_grades(services.grade_log.by_student(student.id))
    sessions = sorted(services.store.list_sessions(student.id), key=lambda s: s.session_date)
    item_ids = {i for s in sessions if s.capsule for i in s.capsule.item_ids}
    stage.result.checkpoints.append(
        {
            "title": title,
            "at": services.clock.now().isoformat(),
            "transcript": [asdict(e) | {"type": type(e).__name__} for e in stage.result.transcript],
            "materials": [
                m.model_dump(mode="json", exclude={"media_ref", "family_id"})
                for m in services.store.list_materials(family.id)
            ],
            "sessions": [s.model_dump(mode="json", exclude={"delivery_message"}) for s in sessions],
            "items": [services.store.get_item(i).model_dump(mode="json") for i in sorted(item_ids)],
            "grades": [g.model_dump(mode="json") for g in grades],
            "mastery": [m.model_dump(mode="json") for m in services.store.list_mastery(student.id)],
            "reviews": [
                r.model_dump(mode="json") for r in services.store.list_quarantine(family.id)
            ],
            "escalations": [
                e.model_dump(mode="json") for e in services.store.list_escalations(family.id)
            ],
            "adaptations": [r.payload for r in services.store.list_records(family.id, "adapt#")],
            "trace": [
                {
                    "at": e.at.isoformat(),
                    "kind": e.kind,
                    "name": e.name,
                    "status": e.status,
                    "duration_ms": e.duration_ms,
                }
                for e in services.telemetry.events
            ],
        }
    )


async def followup(stage, family, student, decision):
    if decision not in {"teacher_note", "reduce_load"}:
        raise ValueError("unsupported demonstration decision")
    services = stage.services
    originals = services.models
    models = {role: LocalPlaybackModel() for role in ModelRole}
    services.models = instrument_models(models, services.telemetry)
    try:
        for day in (2, 3):
            stage.clock.advance(days=1)
            stage.clock.set_time(23)
            stage.note(f"SIMULATED TIME JUMP · day {day}", (("origin", "authored simulation"),))
            models[ModelRole.GENERATE].enqueue(SNIPPET)
            await stage.dispatch(session_event(family.id, student.id, stage.clock.now()))
            for _ in range(3):
                session = active_session(services, student.id)
                item = current_item(services, session) if session else None
                if item is None:
                    stage.beat("followup capsule is complete", "question available", "missing")
                    break
                stage.clock.advance(minutes=2)
                models[ModelRole.STRUCTURED].enqueue(
                    {"action": "continue", "reason": "authored case"}
                )
                state = services.store.get_mastery(student.id, COMPETENCY)
                if state and state.attempts == 8:
                    models[ModelRole.GENERATE].enqueue({"text": NOTE})
                if item.kind is ItemKind.OPEN:
                    models[ModelRole.JUDGE].enqueue(
                        {
                            "correct": False,
                            "rubric_points": 0,
                            "confidence": 0.96,
                            "feedback": "Revisa con un dibujo: sumar arriba y abajo "
                            "cambia la cantidad.",
                        }
                    )
                    await stage.says(
                        CHILD, "Sumé uno arriba y abajo", text="Sumé uno arriba y abajo"
                    )
                else:
                    choice = next(
                        i for i, value in enumerate(item.options) if value != item.answer_key
                    )
                    await stage.says(
                        CHILD,
                        item.options[choice],
                        callback=item_buttons(session.id, item)[choice].callback_data,
                    )
        pending = services.store.list_pending_escalations(family.id)
        stage.beat("persistent difficulty reaches the parent", 1, len(pending))
        checkpoint(stage, family, student, "Día 3 · dificultad persistente")
        if not pending:
            return
        escalation = pending[0]
        label = next(o.label for o in escalation.options if o.key == decision)
        await stage.says(PARENT, label, callback=f"esc:{escalation.id}:{decision}")
        saved = services.store.get_escalation(escalation.id)
        stage.beat("the chosen action is resolved", decision, saved.chosen_option)
        if decision == "teacher_note":
            stage.beat(
                "the drafted note is actually delivered",
                True,
                any(m["text"] == NOTE for m in stage.outbox),
            )
        checkpoint(stage, family, student, "La decisión tiene una consecuencia")
        stage.clock.advance(days=1)
        stage.clock.set_time(23)
        models[ModelRole.GENERATE].enqueue(SNIPPET)
        await stage.dispatch(session_event(family.id, student.id, stage.clock.now()))
        session = active_session(services, student.id)
        size = len(session.capsule.item_ids) if session else 0
        stage.beat(
            "the next scheduled practice reflects the plan",
            1 if decision == "reduce_load" else 3,
            size,
        )
        checkpoint(stage, family, student, "Día 4 · siguiente práctica")
        stage.beat("the complete journey has no runtime failures", 0, len(stage.rejected))
        stage.beat(
            "followup scripts were fully consumed",
            0,
            sum(len(model._script) for model in models.values()),
        )
    finally:
        services.models = originals
