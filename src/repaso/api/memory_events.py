"""Read traces with explicit family/correlation ownership. Cloud logs omit family IDs."""

import threading
import time
from collections import deque
from datetime import UTC, datetime, timedelta
from pathlib import Path

from repaso.api.memory_projection import opaque
from repaso.tools.cloud_trace import trace_events

SAFE_EXTRA = {
    "correlation_id",
    "parent_correlation_id",
    "model_id",
    "evidence_origin",
    "input_tokens",
    "output_tokens",
    "usage_available",
    "call_id",
    "output",
    "intent",
    "record_ref",
    "stop_reason",
    "notes_loaded",
    "approaches_loaded",
}


def owned_events(events, family_id: str, correlations: set[str]) -> list[dict]:
    found = []
    for e in events:
        correlation = e.extra.get("correlation_id", "")
        if e.family_id is not None and e.family_id != family_id:
            continue
        if e.family_id != family_id and correlation not in correlations:
            continue
        found.append(
            {
                "id": opaque(e.model_dump_json()),
                "at": e.at.isoformat(),
                "kind": e.kind,
                "name": e.name,
                "status": e.status,
                "duration_ms": e.duration_ms,
                "extra": {k: v for k, v in e.extra.items() if k in SAFE_EXTRA},
            }
        )
    return sorted(found, key=lambda e: (e["at"], e["id"]))[-100:]


class LocalEventFeed:
    def __init__(self, path: Path):
        self.path = path

    def read(self):
        if not self.path.exists():
            return []
        # Ignore a concurrently incomplete last JSON line.
        with self.path.open() as f:
            return trace_events(deque(f, maxlen=3000))


class CloudEventFeed:
    """Incremental read with overlap for late arrival; provider event IDs deduplicate."""

    def __init__(self, region: str, parameter: str, history_minutes: int = 15):
        import boto3

        self.session = boto3.Session(region_name=region)
        self.parameter = parameter
        self.group = None
        self.client = self.session.client("logs")
        self.start = datetime.now(UTC) - timedelta(minutes=history_minutes)
        self.rows: dict[str, dict] = {}
        self.updated = 0.0
        self.lock = threading.Lock()

    def read(self):
        from repaso.tools.cloud_log_reader import runtime_log_group

        with self.lock:
            if time.monotonic() - self.updated < 5:
                return trace_events(row["message"] for row in self.rows.values())
            if self.group is None:
                arn = self.session.client("ssm").get_parameter(Name=self.parameter)
                self.group = runtime_log_group(arn["Parameter"]["Value"])
            end = datetime.now(UTC)
            request = {
                "logGroupName": self.group,
                "startTime": int(self.start.timestamp() * 1000),
                "endTime": int(end.timestamp() * 1000),
                "filterPattern": '{ $.kind = "*" }',
            }
            seen_tokens = set()
            while True:
                page = self.client.filter_log_events(**request)
                for row in page.get("events", []):
                    self.rows[row["eventId"]] = row
                token = page.get("nextToken")
                if not token or token in seen_tokens:
                    break
                seen_tokens.add(token)
                request["nextToken"] = token
            self.rows = dict(sorted(self.rows.items(), key=lambda p: p[1]["timestamp"])[-3000:])
            # Revisit a 15-minute window: CloudWatch can ingest delayed messages.
            self.start = end - timedelta(minutes=15)
            self.updated = time.monotonic()
            return trace_events(row["message"] for row in self.rows.values())
