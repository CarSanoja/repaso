import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path


def render(event: dict) -> str:
    status = event.get("status", "ok")
    mark = {"completed": "✓", "ok": "✓", "started": "▶", "failed": "✗"}.get(status, "·")
    duration = event.get("duration_ms")
    timing = f" {duration:.0f}ms" if duration else ""
    error = f"  !! {event['error']}" if event.get("error") else ""
    extra = event.get("extra") or {}
    detail = f" [{extra['output']}]" if "output" in extra else ""
    return f"{event['at'][11:19]} {mark} {event['kind']:<5} {event['name']}{detail}{timing}{error}"


def summarize(events: list[dict]) -> str:
    nodes = Counter(
        e["name"] for e in events if e["kind"] == "node" and e["status"] == "completed"
    )
    llm = Counter(e["name"] for e in events if e["kind"] == "llm" and e["status"] == "ok")
    failures = [e for e in events if e["status"] == "failed"]
    lines = ["", "— summary —"]
    lines.append("stages completed: " + ", ".join(f"{k}×{v}" for k, v in sorted(nodes.items())))
    lines.append("llm calls: " + (", ".join(f"{k}×{v}" for k, v in sorted(llm.items())) or "none"))
    lines.append(f"failures: {len(failures)}")
    for failure in failures[:10]:
        lines.append(f"  ✗ {failure['name']}: {failure.get('error')}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(prog="command_center")
    parser.add_argument("--data-dir", default=".local_data/demo_clock")
    parser.add_argument("--follow", action="store_true")
    parser.add_argument("--tail", type=int, default=25)
    args = parser.parse_args()

    path = Path(args.data_dir) / "telemetry.jsonl"
    if not path.exists():
        print(f"no telemetry at {path}")
        return 1

    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    for event in events[-args.tail:]:
        print(render(event))
    print(summarize(events))

    if not args.follow:
        return 0
    with path.open(encoding="utf-8") as handle:
        handle.seek(0, 2)
        while True:
            line = handle.readline()
            if not line:
                time.sleep(0.5)
                continue
            print(render(json.loads(line)))


if __name__ == "__main__":
    sys.exit(main())
