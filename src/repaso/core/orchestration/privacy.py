import json
import os

from repaso.core.orchestration.scheduling import alarm_name
from repaso.schemas.family import FamilyStatus


def forget_family(services, family):
    # Keep a paused profile until every dependent store succeeds. Retrying the
    # command then repeats safe deletes instead of losing the ownership index.
    family.status = FamilyStatus.PAUSED
    services.store.put_family(family)
    services.alarms.remove(alarm_name(family.id))
    students = services.store.list_students(family.id)
    for student in students:
        services.grade_log.forget_student(student.id)
    services.media.delete_prefix(f"media/{family.id}")
    services.store.delete_records(f"chat:{family.chat_ref}")
    if services.settings.local_mode:
        identifiers = {family.id, family.chat_ref, *(s.id for s in students)}
        for filename in ("outbox.jsonl", "events.jsonl", "telemetry.jsonl"):
            path = services.settings.local_data_dir / filename
            if not path.exists():
                continue
            kept = []
            for line in path.read_text().splitlines():
                row = json.loads(line)
                if not _contains(row, identifiers):
                    kept.append(line)
            temp = path.with_suffix(".tmp")
            temp.write_text("".join(line + "\n" for line in kept))
            os.replace(temp, path)
        if hasattr(services.sender, "sent"):
            services.sender.sent[:] = [
                r
                for r in services.sender.sent
                if (r.get("chat_ref") if isinstance(r, dict) else r.chat_ref) != family.chat_ref
            ]
        if hasattr(services.telemetry, "events"):
            services.telemetry.events[:] = [
                event
                for event in services.telemetry.events
                if not _contains(event.model_dump(mode="json"), identifiers)
            ]
    services.store.forget_family(family.id)


def _contains(value, identifiers):
    if isinstance(value, dict):
        return any(_contains(v, identifiers) for v in value.values())
    if isinstance(value, list):
        return any(_contains(v, identifiers) for v in value)
    return isinstance(value, str) and any(i == value or i in value.split("#") for i in identifiers)
