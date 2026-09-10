import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from repaso.config.settings import Settings
from repaso.tools.call_ledger import LedgerFormatError, ledger_path, load_ledger
from repaso.tools.cost_report import build_cost_report
from repaso.tools.cost_table import render_cost_report


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_cost_report")
    parser.add_argument("--ledger", help="Path to a model call ledger written by a run")
    parser.add_argument("--json", help="Write the report as JSON to this path")
    args = parser.parse_args()

    path = Path(args.ledger) if args.ledger else ledger_path(Settings())
    try:
        records = load_ledger(path)
    except LedgerFormatError as error:
        print(error, file=sys.stderr)
        return 1

    report = build_cost_report(records)
    print(f"model call ledger: {path}")
    print(render_cost_report(report))
    if args.json:
        destination = Path(args.json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        print(f"written to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
