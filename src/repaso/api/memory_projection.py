"""An allowlisted, read-only view of learning memory; never raw operational payloads."""

from datetime import UTC, datetime
from hashlib import sha256

from repaso.api.memory_evolution import learning_evolution
from repaso.api.memory_learning import learning_topics
from repaso.schemas.episode import AttemptEpisode
from repaso.schemas.study_session import StudySession
from repaso.schemas.turn import TurnNote
from repaso.tools.grade_log import build_grade_log, effective_grades


def opaque(value: str) -> str:
    return sha256(value.encode()).hexdigest()[:24]


def unexpired(payload: dict, now: datetime) -> bool:
    expiry = payload.get("expires_at")
    return not isinstance(expiry, (int, float)) or expiry > now.timestamp()


def project_memory(container, family_id: str, now: datetime | None = None) -> tuple[dict, set]:
    now = now or datetime.now(UTC)
    store = container.store
    family = store.get_family(family_id)
    if family is None:
        raise LookupError("family_not_found")
    students = store.list_students(family_id)
    student_ids = {s.id for s in students}
    records = store.list_records(family_id)
    chat_records = store.list_records(f"chat:{family.chat_ref}")
    channel_keys = {
        record.key
        for record in chat_records
        if record.key.startswith("channel#")
        and record.payload.get("summary", {}).get("family_id") == family_id
    }
    # Channel replies are delivered in chat scope. The prepared channel result
    # binds each outbox to this family, including when a chat was re-enrolled.
    records += [
        record
        for record in chat_records
        if record.key.startswith("outbox#") and record.key.removeprefix("outbox#") in channel_keys
    ]
    grades = build_grade_log(container.settings)
    assessed = [g for s in students for g in effective_grades(grades.by_student(s.id))]
    mastery = [m.model_dump(mode="json") for s in students for m in store.list_mastery(s.id)]
    sessions = [s for p in students for s in store.list_sessions(p.id)]
    sessions.sort(key=lambda s: (s.session_date, s.id))
    studies, notes, deliveries, adaptations = [], [], [], []
    episode_deliveries = []
    assessment_episodes = []
    correlations = set()
    for record in records:
        payload = record.payload
        if record.key.startswith("pending#invocation#"):
            correlations.add(opaque(record.key.removeprefix("pending#")))
        if record.key.startswith("invocation#"):
            correlations.add(opaque(record.key))
        if record.key.startswith("outbox#"):
            correlations.add(opaque(record.key))
            receipts, messages = payload.get("receipts", []), payload.get("messages", [])
            deliveries.append(
                {
                    "id": opaque(record.key),
                    "at": payload.get("created_at"),
                    "acknowledged": len(receipts),
                    "total": len(messages),
                    "attempts": payload.get("attempts", 0),
                    "status": "acknowledged"
                    if messages and len(receipts) == len(messages)
                    else "pending",
                }
            )
            if unexpired(payload, now):
                for index, message in enumerate(messages):
                    # A record's scope alone is not proof of its destination.
                    # Transport identifiers and button payloads never leave here.
                    if (
                        message.get("chat_ref") == family.chat_ref
                        and message.get("channel") == family.channel.value
                        and isinstance(message.get("text"), str)
                    ):
                        episode_deliveries.append(
                            {
                                "id": f"{opaque(record.key)}-{index}",
                                "delivery_ref": opaque(record.key),
                                "at": payload.get("created_at"),
                                "text": message["text"],
                                "status": "acknowledged" if index < len(receipts) else "pending",
                            }
                        )
        if not unexpired(payload, now):
            continue
        if record.key.startswith("episode#"):
            attempt = AttemptEpisode.model_validate(payload)
            item = store.get_item(attempt.item_id)
            if attempt.student_id in student_ids and item and item.family_id == family_id:
                assessment_episodes.append(
                    {
                        "id": opaque(record.key),
                        "at": attempt.occurred_at.isoformat(),
                        "session_ref": opaque(attempt.session_id),
                        "student_ref": opaque(attempt.student_id),
                        "competency_id": item.competency_id,
                        "content_ref": opaque(item.id),
                        "question": item.stem,
                        "difficulty": item.difficulty,
                        "correct": attempt.correct,
                        "held": attempt.held,
                        "graded_by": attempt.graded_by.value,
                    }
                )
        if record.key.startswith("study#") and payload.get("session"):
            session = StudySession.model_validate(payload["session"])
            if session.student_id in student_ids:
                studies.append(session.model_dump(mode="json"))
        if record.key.startswith("turn#") and payload.get("note"):
            note = TurnNote.model_validate(payload["note"])
            item = store.get_item(note.item_id) if note.item_id else None
            # A corrupt/foreign item reference must not expose another family's page.
            if item and item.family_id != family_id:
                item = None
            notes.append(
                {
                    "id": opaque(record.key),
                    "session_id": record.key.split("#", 2)[1],
                    "session_ref": opaque(record.key.split("#", 2)[1]),
                    "competency_id": item.competency_id if item else None,
                    "content_ref": opaque(item.id) if item else None,
                    "at": note.at.isoformat(),
                    "intent": note.intent.value,
                    "said": note.said,
                    "correct": note.correct,
                    "explained": note.explained,
                    "question": item.stem if item else "",
                    "difficulty": item.difficulty if item else None,
                }
            )
        if record.key.startswith("adapt#") and payload.get("student_id") in student_ids:
            expiry = datetime.fromisoformat(payload["expires_at"])
            if expiry > now:
                adaptations.append(
                    {
                        "student_ref": opaque(payload["student_id"]),
                        **{
                            k: payload.get(k)
                            for k in (
                                "action",
                                "item_limit",
                                "source",
                                "expires_at",
                                "competency_id",
                                "difficulty",
                                "force_open",
                            )
                        },
                    }
                )
    # Channel invocation results are cached in the family's chat scope.
    for record in chat_records:
        if (
            record.key.startswith("invocation#")
            and record.payload.get("result", {}).get("result", {}).get("family_id") == family_id
        ):
            correlations.add(opaque(record.key))
    owners = {s.id: s.student_id for s in sessions}
    owners.update({s["id"]: s["student_id"] for s in studies})
    for n in notes:
        owner = owners.get(n.pop("session_id"))
        n["student_ref"] = opaque(owner) if owner else None
    materials = store.list_materials(family_id)
    decisions = sorted(store.list_escalations(family_id), key=lambda e: e.created_at)
    notes.sort(key=lambda n: (n["at"], n["id"]))
    studies.sort(key=lambda s: (s["opened_at"], s["id"]))
    deliveries.sort(key=lambda d: (d["at"] or "", d["id"]))
    topics = learning_topics(store, family_id, students, assessed, notes, mastery, studies)
    return {
        "family_id": family_id,
        "observed_at": now.isoformat(),
        "source": "local_rehearsal" if container.settings.local_mode else "aws",
        "family": {
            "status": family.status.value,
            "practice_time": family.practice_time.isoformat(),
            "timezone": family.timezone,
        },
        "students": [
            {"student_ref": opaque(s.id), "alias": s.alias, "grade": s.grade} for s in students
        ],
        "counts": {
            "assessed": len(assessed),
            "correct": sum(g.correct is True for g in assessed),
            "held": sum(g.quarantined for g in assessed),
            "explanations": sum(
                n["intent"] == "explanation" and bool(n["explained"]) for n in notes
            ),
        },
        "mastery": mastery,
        "learning_topics": topics,
        "evolution": learning_evolution(
            store, family, students, assessed, notes, topics, decisions, now
        ),
        "notes": notes[-32:],
        "studies": studies[-10:],
        "materials": [
            {
                "id": m.id,
                "status": m.status.value,
                "created_at": m.provenance.created_at.isoformat(),
            }
            for m in materials[-12:]
        ],
        "sessions": [
            {
                "id": s.id,
                "date": s.session_date.isoformat(),
                "status": s.status.value,
                "answered": s.current_item_index,
                "questions": len(s.capsule.item_ids) if s.capsule else len(s.planned_item_ids),
                "delivered_at": s.delivered_at.isoformat() if s.delivered_at else None,
            }
            for s in sessions[-10:]
        ],
        "decisions": [
            {
                "id": d.id,
                "student_ref": opaque(d.student_id) if d.student_id in student_ids else None,
                "competency_id": d.competency_id,
                "kind": d.kind.value,
                "summary": d.summary,
                "status": d.status.value,
                "choice": d.chosen_option,
                "created_at": d.created_at.isoformat(),
                "resolved_at": d.resolved_at.isoformat() if d.resolved_at else None,
                "note": d.drafted_note,
            }
            for d in decisions[-12:]
        ],
        "adaptations": adaptations,
        "deliveries": deliveries[-20:],
        "_episode_deliveries": episode_deliveries,
        "_assessment_episodes": sorted(assessment_episodes, key=lambda a: (a["at"], a["id"]))[-32:],
    }, correlations
