"""Learning evidence grouped by learner and competency, without invented gains."""

from hashlib import sha256

from repaso.core.bank.query import question_key


def ref(value):
    return sha256(value.encode()).hexdigest()[:24]


def learning_topics(store, family_id, students, assessments, notes, mastery, studies):
    rows = {}
    aliases = {s.id: s.alias for s in students}
    student_refs = {ref(s.id): s.id for s in students}
    items = {}

    def topic(student_id, competency):
        key = (student_id, competency)
        if key not in rows:
            label = next(
                (
                    s["goal"]["label"]
                    for s in reversed(studies)
                    if s["student_id"] == student_id
                    and s["goal"]["competency_id"] == competency
                    and s["goal"]["label"]
                ),
                competency.replace("_", " ").replace("-", " "),
            )
            rows[key] = {
                "student_ref": ref(student_id),
                "student": aliases[student_id],
                "competency_id": competency,
                "label": label,
                "assessed": 0,
                "correct": 0,
                "held": 0,
                "explanations": 0,
                "contents": {},
                "difficulties": {},
                "mastery": None,
            }
        return rows[key]

    for grade in assessments:
        if grade.student_id not in aliases:
            continue
        if grade.item_id not in items:
            items[grade.item_id] = store.get_item(grade.item_id)
        item = items[grade.item_id]
        if item is None or item.family_id != family_id:
            continue
        row = topic(grade.student_id, item.competency_id)
        if grade.quarantined or grade.correct is None:
            row["held"] += 1
            continue
        row["assessed"] += 1
        row["correct"] += int(grade.correct)
        content = row["contents"].setdefault(
            question_key(item),
            {
                "content_ref": ref(grade.item_id),
                "content_refs": [],
                "question": item.stem,
                "difficulty": getattr(item, "difficulty", None),
                "assessed": 0,
                "correct": 0,
            },
        )
        if ref(grade.item_id) not in content["content_refs"]:
            content["content_refs"].append(ref(grade.item_id))
        content["assessed"] += 1
        content["correct"] += int(grade.correct)
        level = getattr(item, "difficulty", None)
        if level is not None:
            difficulty = row["difficulties"].setdefault(
                level, {"level": level, "assessed": 0, "correct": 0, "contents": set()}
            )
            difficulty["assessed"] += 1
            difficulty["correct"] += int(grade.correct)
            difficulty["contents"].add(question_key(item))
    for note in notes:
        student = student_refs.get(note["student_ref"])
        if student and note["competency_id"]:
            row = topic(student, note["competency_id"])
            row["explanations"] += int(bool(note["explained"]))
    for state in mastery:
        if state["student_id"] in aliases:
            topic(state["student_id"], state["competency_id"])["mastery"] = {
                key: state[key]
                for key in ("ema_accuracy", "attempts", "level", "last_practiced_at")
            }
    result = []
    for row in rows.values():
        row["distinct_contents"] = len(row["contents"])
        row["repeated_attempts"] = row["assessed"] - row["distinct_contents"]
        row["contents"] = list(row["contents"].values())[-8:]
        row["difficulties"] = [
            {
                "level": d["level"],
                "assessed": d["assessed"],
                "correct": d["correct"],
                "distinct_contents": len(d["contents"]),
            }
            for _, d in sorted(row["difficulties"].items())
        ]
        row["evidence"] = "limited" if row["distinct_contents"] < 3 else "observed"
        row["mastery_basis"] = "current_stored_estimate"
        row["improvement_demonstrated"] = None
        row["domain"] = row["competency_id"].split(".")[0]
        if not row["assessed"]:
            row["summary"] = (
                f"{row['explanations']} explanation(s) retained. "
                "No evaluated response yet; learning improvement is not established."
            )
        else:
            row["summary"] = (
                f"{row['correct']}/{row['assessed']} correct across "
                f"{row['distinct_contents']} distinct question(s). "
                f"{row['repeated_attempts']} repeated-content attempt(s). "
                "This is observed practice evidence, not a measured learning gain."
            )
        result.append(row)
    return sorted(result, key=lambda row: (row["student"], row["label"]))
