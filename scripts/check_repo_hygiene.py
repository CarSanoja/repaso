import re
import subprocess
import sys
from pathlib import Path

FORBIDDEN_PREFIXES = ("private/", ".local_data/", ".venv/", "node_modules/")

FORBIDDEN_NAMES = re.compile(
    r"(^|/)(\.env(\..*)?|.*\.pem|.*\.p12|.*\.pfx|id_rsa|id_ed25519|credentials(\..*)?"
    r"|\.bedrock_agentcore\.yaml)$"
)
ALLOWED_NAMES = re.compile(r"(^|/)\.env\.example$")

SECRET_PATTERNS = {
    "aws access key": r"(AKIA|ASIA)[0-9A-Z]{16}",
    "github token": r"gh[pousr]_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,}",
    "openai key": r"sk-[A-Za-z0-9]{32,}",
    "slack token": r"xox[baprs]-[A-Za-z0-9-]{10,}",
    "private key block": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "telegram bot token": r"[0-9]{9,10}:AA[A-Za-z0-9_-]{33}",
}

REQUIRED_IGNORES = ("private/", ".local_data/", ".env", ".bedrock_agentcore.yaml")

SKIP_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".pdf", ".ico", ".woff", ".woff2")


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=True
    ).stdout
    return [line for line in out.splitlines() if line]


def check_paths(files: list[str]) -> list[str]:
    problems = []
    for path in files:
        if path.startswith(FORBIDDEN_PREFIXES):
            problems.append(f"{path}: lives under a directory that must never be tracked")
        if FORBIDDEN_NAMES.search(path) and not ALLOWED_NAMES.search(path):
            problems.append(f"{path}: filename matches a credential-bearing pattern")
    return problems


def check_secrets(files: list[str], root: Path) -> list[str]:
    problems = []
    for path in files:
        if path.endswith(SKIP_SUFFIXES) or path == "scripts/check_repo_hygiene.py":
            continue
        try:
            text = (root / path).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            match = re.search(pattern, text)
            if match:
                line = text[: match.start()].count("\n") + 1
                problems.append(f"{path}:{line}: looks like a {label}")
    return problems


def check_gitignore(root: Path) -> list[str]:
    ignore = root / ".gitignore"
    if not ignore.exists():
        return [".gitignore: missing"]
    entries = {line.strip() for line in ignore.read_text(encoding="utf-8").splitlines()}
    return [
        f".gitignore: does not cover {needed}"
        for needed in REQUIRED_IGNORES
        if needed not in entries
    ]


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    files = tracked_files()
    problems = check_paths(files) + check_secrets(files, root) + check_gitignore(root)
    if problems:
        print(f"repo hygiene: {len(problems)} problem(s)", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    print(f"repo hygiene: {len(files)} tracked files, no findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
