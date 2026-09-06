from datetime import timedelta
from hashlib import sha256

from repaso.agents.capsule_composer import render_item
from repaso.schemas.common import Lang
from repaso.schemas.item import ItemKind
from repaso.schemas.operation import AdaptationState, OperationRecord

ADAPTIVE_ACTIONS = {"raise_difficulty", "lower_difficulty", "switch_to_open", "reduce_load"}


def apply_adaptation(
    services, family, student_id, competency_id, action, difficulty=2, source="policy"
):
    if action not in ADAPTIVE_ACTIONS:
        return
    key = f"adapt#{student_id}#{competency_id}"
    saved = services.store.get_record(family.id, key)
    state = (
        AdaptationState.model_validate(saved.payload)
        if saved
        else AdaptationState(
            student_id=student_id,
            competency_id=competency_id,
            action=action,
            expires_at=services.clock.now() + timedelta(days=7),
            source=source,
        )
    )
    if saved and state.source == source:
        return
    if state.expires_at <= services.clock.now():
        state = AdaptationState(
            student_id=student_id,
            competency_id=competency_id,
            action=action,
            expires_at=services.clock.now() + timedelta(days=7),
            source=source,
        )
    state.action, state.source = action, source
    state.expires_at = services.clock.now() + timedelta(days=7)
    if action == "switch_to_open":
        state.force_open = True
    elif action == "reduce_load":
        state.item_limit = 1
    else:
        state.difficulty = max(1, min(5, difficulty + (1 if action == "raise_difficulty" else -1)))
    services.store.put_record(
        OperationRecord(scope=family.id, key=key, payload=state.model_dump(mode="json"))
    )


def active_adaptations(services, family, student_id):
    return [
        state
        for record in services.store.list_records(family.id, f"adapt#{student_id}#")
        if (state := AdaptationState.model_validate(record.payload)).expires_at
        > services.clock.now()
    ]


def select_adapted(services, run, items):
    states = active_adaptations(services, run.family, run.student.id)
    selected = list(items)
    for state in states:
        if state.difficulty is None:
            continue
        pool = [i for i in selected if i.competency_id == state.competency_id]
        if pool:
            distance = min(abs(i.difficulty - state.difficulty) for i in pool)
            selected = [
                i
                for i in selected
                if i.competency_id != state.competency_id
                or abs(i.difficulty - state.difficulty) == distance
            ]
    return selected, min([s.item_limit for s in states if s.item_limit] or [4])


def open_variants(services, run, items):
    force = {
        s.competency_id
        for s in active_adaptations(services, run.family, run.student.id)
        if s.force_open
    }
    result = []
    for item in items:
        if item.competency_id in force and item.kind is ItemKind.MCQ:
            prompt = (
                "Explica cómo obtuviste la respuesta. Elegir una opción sin explicar no basta."
                if run.family.lang is Lang.ES
                else "Explain how you found your answer. Choosing an option alone is not enough."
            )
            item = item.model_copy(
                update={
                    "id": sha256(f"open:{run.student.id}:{item.id}".encode()).hexdigest()[:32],
                    "family_id": run.family.id,
                    "variant_of": item.id,
                    "kind": ItemKind.OPEN,
                    "stem": f"{render_item(item)}\n\n{prompt}",
                    "options": [],
                    "rubric": f"Require correct reasoning, not only a choice. {item.rationale}",
                }
            )
            services.store.put_item(item)
        result.append(item)
    return result
