from hashlib import sha256
from zoneinfo import ZoneInfo

from repaso.schemas.family import FamilyStatus
from repaso.schemas.operation import OperationRecord
from repaso.tools.alarms import AlarmSpec, daily_cron


def alarm_name(family_id):
    return "family-" + sha256(family_id.encode()).hexdigest()[:32]


def sync_schedule(services, family):
    ZoneInfo(family.timezone)
    spec = AlarmSpec(
        name=alarm_name(family.id),
        timezone=family.timezone,
        cron=daily_cron(family.practice_time.hour, family.practice_time.minute),
        enabled=family.status not in (FamilyStatus.PAUSED, FamilyStatus.FORGOTTEN),
        payload={"family_id": family.id},
    )
    saved = services.store.get_record(family.id, "schedule")
    body = spec.model_dump(mode="json")
    if saved is not None and saved.payload == body:
        return
    services.alarms.upsert(spec)
    services.store.put_record(OperationRecord(scope=family.id, key="schedule", payload=body))
