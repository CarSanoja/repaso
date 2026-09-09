import argparse
import json
import sys

from teardown_plan import PROJECT, UNKNOWN, Plan, build_plan
from teardown_reader import BotoAccountReader
from teardown_remover import BotoRemover

DEFAULT_REGION = "us-east-1"
UNKNOWN_MODE_NOTE = "deployment mode unknown: only stacks would be removed"
NOTHING = "nothing to remove"


def report(plan: Plan, applying: bool) -> list[str]:
    lines = [f"project {plan.project}, deployment mode {plan.mode}"]
    if plan.blocked:
        return lines + ["refusing to continue:"] + [f"  {line}" for line in plan.refusals]
    if plan.mode == UNKNOWN and plan.storage:
        lines.append(UNKNOWN_MODE_NOTE)
    if plan.empty:
        lines.append(NOTHING)
    else:
        heading = "about to remove" if applying else "would remove"
        lines.append(f"{heading} {len(plan.removes)} resource(s):")
        lines += [f"  {target}" for target in plan.removes]
    if plan.keeps:
        lines.append(f"this teardown does not remove ({len(plan.keeps)}):")
        lines += [f"  {target}" for target in plan.keeps]
    return lines


def as_json(plan: Plan) -> str:
    return json.dumps(
        {
            "project": plan.project,
            "mode": plan.mode,
            "removes": [str(target) for target in plan.removes],
            "keeps": [str(target) for target in plan.keeps],
            "refusals": list(plan.refusals),
        },
        indent=2,
    )


def apply(plan: Plan, remover: BotoRemover):
    if plan.erases_data:
        for bucket in plan.buckets:
            yield f"{bucket}: {remover.empty(bucket)}"
    for stack in plan.stacks:
        yield f"{stack}: {remover.remove(stack)}"
    if plan.erases_data:
        for target in plan.storage:
            yield f"{target}: {remover.remove(target)}"
    for target in plan.keeps:
        yield f"{target}: not removed by this teardown"


def confirmed(plan: Plan, stream=None) -> bool:
    phrase = f"remove {plan.project}"
    print(f"type '{phrase}' to remove {len(plan.removes)} resource(s), anything else to stop")
    try:
        answer = (stream.readline() if stream else input()).strip()
    except EOFError:
        return False
    return answer == phrase


def parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="teardown")
    parser.add_argument("--project", default=PROJECT)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--profile", default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse(argv)
    session = _session(args)
    plan = build_plan(BotoAccountReader(session, args.project), args.project)
    if args.json:
        print(as_json(plan))
    else:
        for line in report(plan, applying=args.apply):
            print(line)
    if plan.blocked:
        return 2
    if not args.apply or plan.empty:
        return 0
    if not confirmed(plan):
        print("teardown cancelled")
        return 1
    for line in apply(plan, BotoRemover(session, args.project)):
        print(line)
    return 0


def _session(args: argparse.Namespace):
    import boto3

    return boto3.Session(profile_name=args.profile, region_name=args.region)


if __name__ == "__main__":
    sys.exit(main())
