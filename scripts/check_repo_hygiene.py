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
    "aws secret access key": r"(?i)aws_secret_access_key\s*[=:]\s*[\"']?[A-Za-z0-9/+=]{40}",
    "github token": r"gh[pousr]_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,}",
    "openai key": r"sk-[A-Za-z0-9]{32,}",
    "anthropic key": r"sk-ant-[A-Za-z0-9_-]{20,}",
    "google api key": r"AIza[0-9A-Za-z_-]{35}",
    "slack token": r"xox[baprs]-[A-Za-z0-9-]{10,}",
    "private key block": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "telegram bot token": r"[0-9]{8,12}:AA[A-Za-z0-9_-]{30,}",
    "json web token": r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
    "international phone number": r"\+(?:1|4[0-9]|5[0-8]|3[0-9]|7|8[0-9]|9[0-9])[ .-]?\d{2,4}"
    r"[ .-]?\d{3}[ .-]?\d{3,4}\b",
}

PLACEHOLDER_ACCOUNTS = frozenset(
    {"123456789012", "111122223333", "000000000000", "012345678901", "210987654321"}
)
ACCOUNT_IN_ARN = re.compile(r"arn:aws[a-z-]*:[a-z0-9-]*:[a-z0-9-]*:(\d{12}):")
ACCOUNT_ASSIGNED = re.compile(r"(?i)account[_-]?id\s*[=:]\s*[\"']?(\d{12})")

REQUIRED_IGNORES = ("private/", ".local_data/", ".env", ".bedrock_agentcore.yaml")

SKIP_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".pdf", ".ico", ".woff", ".woff2", ".mp4")
SELF = ("scripts/check_repo_hygiene.py", "tests/scripts/test_repo_hygiene.py")
MAX_BLOB_BYTES = 2 * 1024 * 1024
MAX_HITS_PER_RULE = 3


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def tracked_files() -> list[str]:
    return [line for line in _git("ls-files").splitlines() if line]


def scannable(path: str) -> bool:
    return not path.endswith(SKIP_SUFFIXES) and path not in SELF


def check_paths(files: list[str]) -> list[str]:
    problems = []
    for path in files:
        if path.startswith(FORBIDDEN_PREFIXES):
            problems.append(f"{path}: lives under a directory that must never be tracked")
        if FORBIDDEN_NAMES.search(path) and not ALLOWED_NAMES.search(path):
            problems.append(f"{path}: filename matches a credential-bearing pattern")
    return problems


def _line_of(text: str, offset: int) -> int:
    return text[:offset].count("\n") + 1


def scan_text(label: str, text: str) -> list[str]:
    problems = []
    for name, pattern in SECRET_PATTERNS.items():
        for match in list(re.finditer(pattern, text))[:MAX_HITS_PER_RULE]:
            problems.append(f"{label}:{_line_of(text, match.start())}: looks like a {name}")
    for pattern, kind in ((ACCOUNT_IN_ARN, "arn"), (ACCOUNT_ASSIGNED, "assignment")):
        for match in list(pattern.finditer(text))[:MAX_HITS_PER_RULE]:
            if match.group(1) not in PLACEHOLDER_ACCOUNTS:
                problems.append(
                    f"{label}:{_line_of(text, match.start())}: "
                    f"carries a real-looking account id in an {kind}"
                )
    return problems


def check_secrets(files: list[str], root: Path) -> list[str]:
    problems = []
    for path in files:
        if not scannable(path):
            continue
        try:
            text = (root / path).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        problems.extend(scan_text(path, text))
    return problems


def readable_blobs(candidates: dict[str, str]) -> dict[str, str]:
    if not candidates:
        return {}
    request = "\n".join(candidates) + "\n"
    result = subprocess.run(
        ["git", "cat-file", "--batch-check"],
        input=request.encode(),
        capture_output=True,
        check=True,
    )
    kept: dict[str, str] = {}
    for line in result.stdout.decode().splitlines():
        fields = line.split()
        if len(fields) != 3 or fields[1] != "blob" or int(fields[2]) > MAX_BLOB_BYTES:
            continue
        kept[fields[0]] = candidates[fields[0]]
    return kept


def history_blobs(every_ref: bool = False) -> list[tuple[str, str]]:
    scope = "--all" if every_ref else "HEAD"
    seen: dict[str, str] = {}
    for line in _git("rev-list", "--objects", scope).splitlines():
        sha, _, path = line.partition(" ")
        if path and scannable(path) and sha not in seen:
            seen[sha] = path
    return sorted(readable_blobs(seen).items())


def read_blobs(blobs: list[tuple[str, str]]) -> dict[str, str]:
    if not blobs:
        return {}
    request = "\n".join(sha for sha, _ in blobs) + "\n"
    result = subprocess.run(
        ["git", "cat-file", "--batch"],
        input=request.encode(),
        capture_output=True,
        check=True,
    )
    contents: dict[str, str] = {}
    stream = result.stdout
    cursor = 0
    while cursor < len(stream):
        end = stream.find(b"\n", cursor)
        if end == -1:
            break
        sha, kind, size = stream[cursor:end].decode().split()
        cursor = end + 1
        body = stream[cursor : cursor + int(size)]
        cursor += int(size) + 1
        if kind == "blob" and len(body) <= MAX_BLOB_BYTES:
            contents[sha] = body.decode("utf-8", errors="ignore")
    return contents


def check_history(every_ref: bool = False) -> list[str]:
    blobs = history_blobs(every_ref)
    contents = read_blobs(blobs)
    problems = []
    for sha, path in blobs:
        text = contents.get(sha)
        if text is not None:
            problems.extend(scan_text(f"history {sha[:12]} {path}", text))
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


def main(every_ref: bool = False) -> int:
    root = Path(__file__).resolve().parent.parent
    files = tracked_files()
    blobs = history_blobs(every_ref)
    history = check_history(every_ref)
    problems = check_paths(files) + check_secrets(files, root) + check_gitignore(root) + history
    if problems:
        print(f"repo hygiene: {len(problems)} problem(s)", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    scope = "every ref" if every_ref else "this branch"
    print(
        f"repo hygiene: {len(files)} tracked files, "
        f"{len(blobs)} historical blobs on {scope}, no findings"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--all" in sys.argv))
