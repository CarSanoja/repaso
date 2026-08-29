import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CHECKS = (("ruff", ["ruff", "check", "."]), ("pytest", ["pytest", "-q"]))


def commits(base: str) -> list[str]:
    out = subprocess.run(
        ["git", "rev-list", "--reverse", f"{base}..HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [line for line in out.splitlines() if line]


def subject(sha: str) -> str:
    return subprocess.run(
        ["git", "log", "-1", "--format=%s", sha], capture_output=True, text=True, check=True
    ).stdout.strip()


def verify(sha: str, python: str) -> list[str]:
    root = Path(tempfile.mkdtemp(prefix="verify-"))
    tree = root / "tree"
    failures = []
    try:
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(tree), sha],
            capture_output=True,
            check=True,
        )
        for name, command in CHECKS:
            result = subprocess.run(
                [python, "-m", *command], cwd=tree, capture_output=True, text=True
            )
            if result.returncode != 0:
                tail = (result.stdout + result.stderr).strip().splitlines()[-1:]
                failures.append(f"{name}: {tail[0] if tail else 'failed'}")
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(tree)], capture_output=True
        )
        shutil.rmtree(root, ignore_errors=True)
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args()

    pending = commits(args.base)
    if not pending:
        print(f"nothing to verify against {args.base}")
        return 0

    red = 0
    for sha in pending:
        failures = verify(sha, args.python)
        mark = "ok  " if not failures else "FAIL"
        print(f"{mark} {sha[:8]}  {subject(sha)}")
        for failure in failures:
            print(f"       {failure}")
        red += bool(failures)
    print(f"{len(pending) - red}/{len(pending)} commits green")
    return 1 if red else 0


if __name__ == "__main__":
    raise SystemExit(main())
