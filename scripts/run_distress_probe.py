import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from repaso.agents.turn_reader import read_turn
from repaso.config.models import ModelRole, model_for
from repaso.config.settings import Settings
from repaso.core.harness.clock import SystemClock
from repaso.schemas.common import Lang
from repaso.schemas.turn import PracticeState, TurnContext, TurnIntent
from repaso.tools.guardrails import BedrockGuardrailsScreener
from repaso.tools.llm import build_model
from tests.distress_corpus import (
    DISTRESS_LINES,
    ORDINARY_LINES,
    PRACTICE_LINES,
    REFUSED_LINES,
)

CONTEXT = TurnContext(
    lang=Lang.ES,
    grade=4,
    competency="Fracciones equivalentes",
    practice=PracticeState.OPEN,
    question="¿Qué fracción equivale a 1/2?",
    options=["2/4", "1/3", "3/5"],
    items_left=2,
)


def screen_rows(screener: BedrockGuardrailsScreener, lines: tuple[str, ...]) -> list[dict]:
    rows = []
    for text in lines:
        verdict = screener.screen(text)
        rows.append(
            {
                "text": text,
                "safe": verdict.safe,
                "reasons": verdict.reasons,
                "reply": verdict.reply,
            }
        )
    return rows


async def read_rows(model, lines: tuple[str, ...], expected: str, samples: int) -> list[dict]:
    rows = []
    for text in lines:
        intents = []
        for _ in range(samples):
            decision = await read_turn(text, CONTEXT, model)
            intents.append("unread" if decision is None else decision.intent.value)
        rows.append(
            {
                "text": text,
                "expected": expected,
                "read_as": intents,
                "met": sum(1 for intent in intents if intent == expected),
                "samples": samples,
            }
        )
    return rows


async def collect(args) -> dict:
    settings = Settings(aws_region=args.region, local_mode=False)
    screener = BedrockGuardrailsScreener(args.guardrail_id, args.guardrail_version)
    model = build_model(ModelRole.STRUCTURED, settings)
    practice = []
    for text, intent in PRACTICE_LINES:
        practice.extend(await read_rows(model, (text,), intent.value, args.samples))
    return {
        "measured_at": SystemClock().now().isoformat(),
        "region": args.region,
        "guardrail_version": args.guardrail_version,
        "reader_model_id": model_for(ModelRole.STRUCTURED),
        "samples_per_line": args.samples,
        "guardrail_on_distress": screen_rows(screener, DISTRESS_LINES),
        "guardrail_on_refused": screen_rows(screener, REFUSED_LINES),
        "guardrail_on_ordinary": screen_rows(screener, ordinary_lines()),
        "reader_on_distress": await read_rows(
            model, DISTRESS_LINES, TurnIntent.DISTRESS.value, args.samples
        ),
        "reader_on_practice": practice,
        "reader_on_ordinary": await read_rows(model, ORDINARY_LINES, "", args.samples),
    }


def ordinary_lines() -> tuple[str, ...]:
    return tuple(text for text, _ in PRACTICE_LINES) + ORDINARY_LINES


def summarize(report: dict) -> list[str]:
    lines = []
    stopped = sum(1 for row in report["guardrail_on_distress"] if not row["safe"])
    carried = sum(1 for row in report["guardrail_on_refused"] if row["reply"])
    ordinary = report["guardrail_on_ordinary"]
    stopped_ordinary = sum(1 for row in ordinary if not row["safe"])
    lines.append(
        f"guardrail stopped {stopped}/{len(report['guardrail_on_distress'])} distress lines, "
        f"{stopped_ordinary}/{len(ordinary)} ordinary lines, "
        f"and offered a reply on {carried}/{len(report['guardrail_on_refused'])} refusals"
    )
    for key in ("reader_on_distress", "reader_on_practice", "reader_on_ordinary"):
        met = sum(row["met"] for row in report[key])
        calls = sum(row["samples"] for row in report[key])
        alarms = sum(row["read_as"].count(TurnIntent.DISTRESS.value) for row in report[key])
        lines.append(f"{key}: {met}/{calls} read as expected, {alarms}/{calls} read as distress")
        for row in report[key]:
            lines.append(f"  {row['met']}/{row['samples']} {row['expected']:<18}{row['text']}")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_distress_probe")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--guardrail-id", required=True)
    parser.add_argument("--guardrail-version", default="1")
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--out", type=Path, default=Path(".local_data/live/distress.json"))
    args = parser.parse_args()

    report = asyncio.run(collect(args))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n".join(summarize(report)))
    print(f"written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
