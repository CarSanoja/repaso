import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from repaso.config.settings import Settings
from repaso.tools.cloud_log_reader import (
    read_messages,
    resolve_runtime_arn,
    runtime_log_group,
)
from repaso.tools.cloud_trace import call_records, hops, trace_events
from repaso.tools.cost_report import build_cost_report
from repaso.tools.cost_table import render_cost_report

HOP_HEADER = f"{'at':24} {'kind':12} {'name':28} {'status':10} {'ms':>9}"
CALL_HEADER = (
    f"{'at':24} {'role':11} {'call':18} {'model':46} "
    f"{'in':>7} {'out':>7} {'ms':>9} {'usd':>10} {'end':<12} outcome"
)


def parse_moment(raw: str) -> datetime:
    return datetime.fromisoformat(raw).astimezone(UTC)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="reconstruct_cloud_journey")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--log-group", help="Defaults to the deployed runtime's own group")
    parser.add_argument("--since-minutes", type=int, default=120)
    parser.add_argument("--start", type=parse_moment, help="ISO instant; overrides --since-minutes")
    parser.add_argument("--end", type=parse_moment, help="ISO instant; defaults to now")
    parser.add_argument("--json", help="Write the reconstruction to this path")
    return parser.parse_args()


def window(args: argparse.Namespace) -> tuple[datetime, datetime]:
    end = args.end or datetime.now(UTC)
    return args.start or end - timedelta(minutes=args.since_minutes), end


def group_name(args: argparse.Namespace, settings: Settings) -> str:
    if args.log_group:
        return args.log_group
    arn = settings.agentcore_runtime_arn or resolve_runtime_arn(
        args.region, settings.agentcore_runtime_arn_parameter
    )
    return runtime_log_group(arn)


def print_hops(events) -> None:
    print(HOP_HEADER)
    for event in hops(events):
        duration = f"{event.duration_ms:9.1f}" if event.duration_ms is not None else " " * 9
        print(
            f"{event.at.isoformat():24} {event.kind:12} {event.name:28} "
            f"{event.status:10} {duration}"
        )


def print_calls(records) -> None:
    print(CALL_HEADER)
    for record in records:
        usage = record.usage
        cost = record.cost
        print(
            f"{record.at.isoformat():24} {record.role:11} {record.kind:18} {record.model_id:46} "
            f"{usage.input_tokens if usage else 0:7} {usage.output_tokens if usage else 0:7} "
            f"{record.latency_ms:9.1f} {cost.total_usd if cost else 0.0:10.6f} "
            f"{record.stop_reason or '-':<12} {record.outcome.value}"
        )


def main() -> int:
    args = arguments()
    settings = Settings()
    start, end = window(args)
    group = group_name(args, settings)
    messages = read_messages(args.region, group, start, end)
    events = trace_events(messages)
    records = call_records(events)
    report = build_cost_report(records)

    print(f"log group: {group}")
    print(f"window: {start.isoformat()} to {end.isoformat()}")
    print(f"{len(messages)} log lines, {len(events)} traces, {len(records)} model calls\n")
    print_hops(events)
    print()
    print_calls(records)
    print()
    print(render_cost_report(report))

    if args.json:
        destination = Path(args.json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(
                {
                    "log_group": group,
                    "window": {"start": start.isoformat(), "end": end.isoformat()},
                    "log_lines": len(messages),
                    "hops": [event.model_dump(mode="json") for event in hops(events)],
                    "calls": [record.model_dump(mode="json") for record in records],
                    "report": report.model_dump(mode="json"),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"written to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
