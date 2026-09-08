"""Read-only readiness check for a repaso deployment. Creates and changes nothing."""

import argparse
import sys
from typing import Any

import preflight_account as account
import preflight_names as names
from preflight_findings import AwsSession, Finding, Status

HEADER = "repaso deploy preflight: region {region}, bootstrap qualifier {qualifier}"
CLEAR = "nothing blocks a deployment; every warning above is still yours to read"
BLOCKED = "fix every blocker above before deploying:"


def build_session(profile: str | None, region: str) -> AwsSession:
    import boto3

    return boto3.Session(profile_name=profile, region_name=region)


def collect(session: AwsSession, inference: bool = True) -> list[Finding]:
    found = [account.identity(session)]
    if found[0].status is Status.BLOCKER:
        return found
    found.append(account.region(session))
    found.append(account.bootstrap(session))
    found.extend(account.models(session))
    if inference:
        found.append(account.inference(session))
    found.append(account.docker())
    found.extend(names.secrets(session))
    found.extend(names.taken(session))
    found.extend(names.stacks(session))
    return found


def _lines(findings: list[Finding]) -> list[str]:
    lines = [HEADER.format(region=account.REGION, qualifier=account.QUALIFIER)]
    for finding in findings:
        lines.append(f"  {finding.status.value:<8} {finding.check:<42} {finding.detail}")
        if finding.remedy:
            lines.append(f"  {'':<8} -> {finding.remedy}")
    return lines


def report(findings: list[Finding], stream: Any) -> int:
    blockers = [finding for finding in findings if finding.status is Status.BLOCKER]
    warnings = [finding for finding in findings if finding.status is Status.WARN]
    lines = _lines(findings)
    lines.append(f"\n{len(blockers)} blocker(s), {len(warnings)} warning(s)")
    lines.append(BLOCKED if blockers else CLEAR)
    lines.extend(f"  - {finding.check}: {finding.detail}" for finding in blockers)
    print("\n".join(lines), file=stream)
    return 1 if blockers else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="preflight_deploy")
    parser.add_argument("--profile", default=None)
    parser.add_argument("--region", default=account.REGION)
    parser.add_argument("--no-inference", action="store_true")
    args = parser.parse_args(argv)
    session = build_session(args.profile, args.region)
    return report(collect(session, inference=not args.no_inference), sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
