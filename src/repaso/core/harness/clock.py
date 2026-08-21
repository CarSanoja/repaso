from datetime import UTC, date, datetime, timedelta
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...

    def today(self) -> date: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def today(self) -> date:
        return self.now().date()


class SimClock:
    def __init__(self, start: datetime) -> None:
        if start.tzinfo is None:
            raise ValueError("SimClock start must be timezone-aware")
        self._now = start

    def now(self) -> datetime:
        return self._now

    def today(self) -> date:
        return self._now.date()

    def advance(self, days: int = 0, hours: int = 0, minutes: int = 0) -> datetime:
        self._now = self._now + timedelta(days=days, hours=hours, minutes=minutes)
        return self._now

    def set_time(self, hour: int, minute: int = 0) -> datetime:
        self._now = self._now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return self._now
