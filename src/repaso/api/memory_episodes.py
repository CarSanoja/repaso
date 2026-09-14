"""Reconstruct retained learning episodes using explicit trace links, never proximity."""

from repaso.core.orchestration.turn_memory import MAX_NOTES


def _count(event, name):
    try:
        return max(0, int(event["extra"][name]))
    except (TypeError, ValueError, KeyError):
        return None


def learning_episodes(
    notes: list[dict],
    events: list[dict],
    deliveries: list[dict],
    assessments: list[dict] | None = None,
) -> list[dict]:
    """Outgoing text requires a verified turn-to-delivery chain.

    The incoming side is a retained snippet (up to 160 characters), not a full
    Telegram export. Previous approaches describe the reconstructed retained
    window; telemetry independently proves how many approaches were loaded.
    """
    episodes = []
    ordered = sorted(notes, key=lambda n: (n["at"], n["id"]))
    for index, note in enumerate(ordered):
        saved = next(
            (
                e
                for e in events
                if e["kind"] == "memory"
                and e["name"] == "turn.saved"
                and e["extra"].get("record_ref") == note["id"]
                and e["extra"].get("correlation_id")
            ),
            None,
        )
        correlation = saved["extra"]["correlation_id"] if saved else None
        linked = (
            [
                e
                for e in events
                if e["extra"].get("correlation_id") == correlation
                or e["extra"].get("parent_correlation_id") == correlation
            ]
            if correlation
            else []
        )
        delivery_refs = {
            e["extra"].get("correlation_id")
            for e in linked
            if e["kind"] == "delivery" and e["extra"].get("parent_correlation_id") == correlation
        }
        outgoing = [d for d in deliveries if d["delivery_ref"] in delivery_refs]
        context = next((e for e in linked if e["name"] == "explanation.context_loaded"), {})
        approaches_loaded = _count(context, "approaches_loaded")
        notes_loaded = _count(context, "notes_loaded")
        previous = [
            n
            for n in ordered[:index]
            if n.get("session_ref")
            and n.get("session_ref") == note.get("session_ref")
            and n["at"] < note["at"]
        ][-MAX_NOTES:]
        approaches = {}
        for prior in previous:
            if prior.get("explained"):
                approaches.setdefault(
                    prior["explained"], {"note_id": prior["id"], "approach": prior["explained"]}
                )
        # A bounded or expired snapshot may not reconstruct the window. Show
        # the logged count without guessing which missing approaches it means.
        previous_approaches = (
            list(approaches.values())
            if approaches_loaded == len(approaches) and notes_loaded == len(previous)
            else []
        )
        conversation = []
        if note.get("said"):
            conversation.append(
                {
                    "id": note["id"] + "-incoming",
                    "role": "student",
                    "text": note["said"],
                    "at": note["at"],
                    "source": "retained_turn",
                    "status": "retained_snippet",
                }
            )
        conversation.extend(
            {
                "id": d["id"],
                "role": "agent",
                "text": d["text"],
                "at": d["at"],
                "source": "delivery_record",
                "status": d["status"],
            }
            for d in sorted(outgoing, key=lambda d: (d["at"] or "", d["id"]))
        )
        outcome = "recorded"
        if note["intent"] == "explanation":
            outcome = "explained" if note["explained"] else "help_unavailable"
        elif note.get("correct") is not None:
            outcome = "assessed"
        episodes.append(
            {
                **{
                    key: note.get(key)
                    for key in (
                        "id",
                        "at",
                        "student_ref",
                        "competency_id",
                        "content_ref",
                        "question",
                        "difficulty",
                        "intent",
                        "correct",
                    )
                },
                "conversation": conversation,
                "events": linked,
                "memory": {
                    "notes_loaded": notes_loaded,
                    "approaches_loaded": approaches_loaded,
                    "previous_approaches": previous_approaches,
                    "previous_approaches_source": "reconstructed_retained_window",
                    "saved_approach": note["explained"],
                    "correlation_verified": bool(correlation),
                },
                "outcome": outcome,
                "reconstruction": "correlated" if outgoing else "partial",
                "transcript_complete": False,
            }
        )
    answered = {
        (n.get("session_ref"), n.get("content_ref"))
        for n in notes
        if n["intent"] == "answer" and n.get("correct") is not None
    }
    for assessment in assessments or []:
        if (assessment["session_ref"], assessment["content_ref"]) in answered:
            continue
        episodes.append(
            {
                **{k: v for k, v in assessment.items() if k != "session_ref"},
                "intent": "answer",
                "conversation": [],
                "events": [],
                "memory": {
                    "notes_loaded": None,
                    "approaches_loaded": None,
                    "previous_approaches": [],
                    "previous_approaches_source": "reconstructed_retained_window",
                    "saved_approach": "",
                    "correlation_verified": False,
                },
                "outcome": "held"
                if assessment["held"] or assessment["correct"] is None
                else "assessed",
                "assessment_source": "attempt_record",
                "reconstruction": "partial",
                "transcript_complete": False,
            }
        )
    return sorted(episodes, key=lambda e: (e["at"], e["id"]))
