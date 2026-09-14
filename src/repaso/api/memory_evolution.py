"""Observed practice history and stored review dates, without synthetic mastery history."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from repaso.api.memory_learning import ref
from repaso.core.bank.query import question_key
from repaso.core.orchestration.turn_memory import WINDOW_TTL_DAYS

WINDOW_DAYS = 30


def learning_evolution(store, family, students, assessments, notes, topics, decisions, now):
    timezone = ZoneInfo(family.timezone)
    end = now.astimezone(timezone).date()
    start = end - timedelta(days=WINDOW_DAYS - 1)
    learners = {s.id: s for s in students if s.family_id == family.id}
    learner_refs = {ref(s.id): s for s in learners.values()}
    items, observations, reviews, choices = {}, [], [], []

    def item_for(item_id):
        if item_id not in items:
            item = store.get_item(item_id)
            items[item_id] = item if item and item.family_id == family.id else None
        return items[item_id]

    def local_day(at):
        if isinstance(at, str):
            at = datetime.fromisoformat(at)
        if at.tzinfo is None:
            at = at.replace(tzinfo=UTC)
        return at.astimezone(timezone).date()

    # The caller supplies the full effective grade log, not the 32-note or
    # event-stream preview. Grade replacement is resolved before this step.
    seen_grades = set()
    for grade in assessments:
        item = item_for(grade.item_id)
        if grade.student_id not in learners or item is None:
            continue
        identity = (grade.student_id, grade.item_id, grade.id or grade.graded_at.isoformat())
        if identity in seen_grades:
            continue
        seen_grades.add(identity)
        day = local_day(grade.responded_at or grade.graded_at)
        if day > end:
            continue
        held = grade.quarantined or grade.correct is None
        observations.append(
            {
                "student_ref": ref(grade.student_id),
                "competency_id": item.competency_id,
                "date": day,
                "assessed": int(not held),
                "correct": int(not held and grade.correct is True),
                "held": int(held),
                "help_requests": 0,
                "explanations": 0,
                "content": (item.competency_id, question_key(item)) if not held else None,
            }
        )
    seen_notes = set()
    for note in notes:
        if (
            note["student_ref"] not in learner_refs
            or note["intent"] != "explanation"
            or note["id"] in seen_notes
        ):
            continue
        seen_notes.add(note["id"])
        day = local_day(note["at"])
        if day > end:
            continue
        observations.append(
            {
                "student_ref": note["student_ref"],
                "competency_id": note["competency_id"],
                "date": day,
                "assessed": 0,
                "correct": 0,
                "held": 0,
                "help_requests": 1,
                "explanations": int(bool(note["explained"])),
                "content": None,
            }
        )
    for student in learners.values():
        for state in store.list_spaced(student.id):
            item = item_for(state.item_id)
            if state.student_id != student.id or item is None:
                continue
            reviews.append(
                {
                    "student_ref": ref(student.id),
                    "content_ref": ref(item.id),
                    "question": item.stem,
                    "competency_id": item.competency_id,
                    "difficulty": item.difficulty,
                    "due_date": state.due_date.isoformat(),
                    "interval_days": state.interval_days,
                    "repetitions": state.repetitions,
                    "overdue": state.due_date < end,
                    "source": "stored_spaced_review",
                }
            )
    for decision in decisions:
        if decision.family_id != family.id or (
            decision.student_id is not None and decision.student_id not in learners
        ):
            continue
        choices.append(
            {
                "id": ref(decision.id),
                "student_ref": ref(decision.student_id) if decision.student_id else None,
                "competency_id": decision.competency_id,
                "kind": decision.kind.value,
                "status": decision.status.value,
                "choice": decision.chosen_option,
                "created_at": decision.created_at.isoformat(),
                "resolved_at": decision.resolved_at.isoformat() if decision.resolved_at else None,
            }
        )
    labels = {(t["student_ref"], t["competency_id"]): t["label"] for t in topics}
    groups = {(None, None), *((ref(s.id), None) for s in learners.values())}
    groups.update((o["student_ref"], o["competency_id"]) for o in observations + reviews)
    groups.update(labels)
    groups.update((None, competency) for _, competency in list(groups) if competency)
    series = []
    for student_ref, competency_id in sorted(groups, key=lambda key: (key[0] or "", key[1] or "")):

        def belongs(row, student_ref=student_ref, competency_id=competency_id):
            return (student_ref is None or row["student_ref"] == student_ref) and (
                competency_id is None or row["competency_id"] == competency_id
            )

        selected = [o for o in observations if belongs(o)]
        before = [o for o in selected if o["date"] < start]
        baseline = _totals(before)
        cumulative = dict(baseline)
        contents = {o["content"] for o in before if o["content"] is not None}
        days = []
        for offset in range(WINDOW_DAYS):
            day = start + timedelta(days=offset)
            activity = [o for o in selected if o["date"] == day]
            daily = _totals(activity)
            for key in ("assessed", "correct"):
                cumulative[key] += daily[key]
            contents.update(o["content"] for o in activity if o["content"] is not None)
            days.append(
                {
                    "date": day.isoformat(),
                    **daily,
                    "cumulative_assessed": cumulative["assessed"],
                    "cumulative_correct": cumulative["correct"],
                    "cumulative_distinct_contents": len(contents),
                    "active": bool(activity),
                }
            )
        active_dates = sorted({o["date"] for o in selected})
        learner = learner_refs.get(student_ref)
        matching_reviews = sorted(
            (r for r in reviews if belongs(r)), key=lambda r: (r["due_date"], r["content_ref"])
        )
        series.append(
            {
                "student_ref": student_ref,
                "competency_id": competency_id,
                "student": learner.alias if learner else "Family",
                "label": labels.get(
                    (student_ref, competency_id),
                    next(
                        (label for (_, comp), label in labels.items() if comp == competency_id),
                        competency_id or "All topics",
                    ),
                ),
                "summary": {
                    **_totals(selected),
                    "active_days": len(active_dates),
                    "first_activity": active_dates[0].isoformat() if active_dates else None,
                    "last_activity": active_dates[-1].isoformat() if active_dates else None,
                },
                "window_summary": _totals([o for o in selected if o["date"] >= start]),
                "baseline": baseline,
                "days": days,
                "next_reviews": matching_reviews[:12],
                "review_count": len(matching_reviews),
                "adult_decisions": sorted(
                    (d for d in choices if belongs(d)), key=lambda d: d["created_at"]
                )[-12:],
                "history_status": "no_activity"
                if not active_dates
                else ("single_day" if len(active_dates) == 1 else "multiple_days"),
            }
        )
    return {
        "timezone": family.timezone,
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "window_days": WINDOW_DAYS,
        "help_history_retention_days": WINDOW_TTL_DAYS,
        "help_history_complete": False,
        "history_basis": "effective_assessments_and_retained_help",
        "mastery_history_available": False,
        "series": series,
    }


def _totals(observations):
    result = {
        key: sum(o[key] for o in observations)
        for key in ("assessed", "correct", "held", "help_requests", "explanations")
    }
    result["distinct_contents"] = len(
        {o["content"] for o in observations if o["content"] is not None}
    )
    return result
