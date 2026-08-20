import json
import os
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from repaso.config.settings import Settings
from repaso.schemas.common import FrozenStrictModel

ALARMS_FILE = "alarms.json"
STATE_ENABLED = "ENABLED"
STATE_DISABLED = "DISABLED"


class AlarmSpec(FrozenStrictModel):
    name: str
    cron: str
    enabled: bool = True
    payload: dict[str, str] = {}


@runtime_checkable
class AlarmScheduler(Protocol):
    def upsert(self, spec: AlarmSpec) -> None: ...

    def remove(self, name: str) -> None: ...

    def list_alarms(self) -> list[AlarmSpec]: ...

    def set_enabled(self, name: str, enabled: bool) -> None: ...


def daily_cron(hour: int, minute: int) -> str:
    if not 0 <= hour <= 23:
        raise ValueError("hour must be between 0 and 23")
    if not 0 <= minute <= 59:
        raise ValueError("minute must be between 0 and 59")
    return f"cron({minute} {hour} * * ? *)"


class LocalAlarmScheduler:
    def __init__(self, settings: Settings) -> None:
        self._path = Path(settings.local_data_dir) / ALARMS_FILE

    def upsert(self, spec: AlarmSpec) -> None:
        alarms = self._load()
        alarms[spec.name] = spec
        self._write(alarms)

    def remove(self, name: str) -> None:
        alarms = self._load()
        if alarms.pop(name, None) is None:
            return
        self._write(alarms)

    def list_alarms(self) -> list[AlarmSpec]:
        alarms = self._load()
        return [alarms[name] for name in sorted(alarms)]

    def set_enabled(self, name: str, enabled: bool) -> None:
        alarms = self._load()
        spec = alarms.get(name)
        if spec is None:
            raise KeyError(name)
        alarms[name] = spec.model_copy(update={"enabled": enabled})
        self._write(alarms)

    def _load(self) -> dict[str, AlarmSpec]:
        if not self._path.exists():
            return {}
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        return {name: AlarmSpec.model_validate(entry) for name, entry in raw.items()}

    def _write(self, alarms: dict[str, AlarmSpec]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        body = {name: alarms[name].model_dump(mode="json") for name in sorted(alarms)}
        staged = self._path.with_name(f"{self._path.name}.tmp")
        staged.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(staged, self._path)


class SchedulerAlarms:
    def __init__(self, settings: Settings, target_arn: str = "", role_arn: str = "") -> None:
        self._group = settings.scheduler_group
        self._target_arn = target_arn
        self._role_arn = role_arn

    def upsert(self, spec: AlarmSpec) -> None:
        client = self._client()
        request = self._request(spec)
        try:
            client.update_schedule(**request)
        except client.exceptions.ResourceNotFoundException:
            client.create_schedule(**request)

    def remove(self, name: str) -> None:
        client = self._client()
        try:
            client.delete_schedule(Name=name, GroupName=self._group)
        except client.exceptions.ResourceNotFoundException:
            return

    def list_alarms(self) -> list[AlarmSpec]:
        client = self._client()
        specs: list[AlarmSpec] = []
        token: str | None = None
        while True:
            request: dict[str, Any] = {"GroupName": self._group}
            if token:
                request["NextToken"] = token
            page = client.list_schedules(**request)
            for entry in page.get("Schedules", []):
                specs.append(self._describe(client, entry["Name"]))
            token = page.get("NextToken")
            if not token:
                return specs

    def set_enabled(self, name: str, enabled: bool) -> None:
        client = self._client()
        spec = self._describe(client, name)
        self.upsert(spec.model_copy(update={"enabled": enabled}))

    def _describe(self, client: Any, name: str) -> AlarmSpec:
        described = client.get_schedule(Name=name, GroupName=self._group)
        raw = json.loads(described.get("Target", {}).get("Input") or "{}")
        return AlarmSpec(
            name=described["Name"],
            cron=described["ScheduleExpression"],
            enabled=described.get("State", STATE_ENABLED) == STATE_ENABLED,
            payload={str(key): str(value) for key, value in raw.items()},
        )

    def _request(self, spec: AlarmSpec) -> dict[str, Any]:
        return {
            "Name": spec.name,
            "GroupName": self._group,
            "ScheduleExpression": spec.cron,
            "FlexibleTimeWindow": {"Mode": "OFF"},
            "State": STATE_ENABLED if spec.enabled else STATE_DISABLED,
            "Target": {
                "Arn": self._target_arn,
                "RoleArn": self._role_arn,
                "Input": json.dumps(spec.payload, ensure_ascii=False, sort_keys=True),
            },
        }

    def _client(self) -> Any:
        from repaso.config.clients import scheduler_client

        return scheduler_client()


def build_alarm_scheduler(
    settings: Settings, target_arn: str = "", role_arn: str = ""
) -> AlarmScheduler:
    if settings.local_mode:
        return LocalAlarmScheduler(settings)
    return SchedulerAlarms(settings, target_arn=target_arn, role_arn=role_arn)
