import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "check_repo_hygiene", ROOT / "scripts" / "check_repo_hygiene.py"
)
hygiene = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(hygiene)


def test_the_repository_as_it_stands_is_clean():
    assert hygiene.main() == 0


@pytest.mark.parametrize(
    "path",
    [
        "private/architecture.md",
        ".local_data/events.jsonl",
        ".env",
        ".env.production",
        "keys/server.pem",
        "deploy/id_rsa",
        ".bedrock_agentcore.yaml",
    ],
)
def test_paths_that_must_never_be_tracked_are_rejected(path):
    assert hygiene.check_paths([path])


@pytest.mark.parametrize(
    "path", [".env.example", "docs/product/README.md", "src/repaso/api/main.py"]
)
def test_legitimate_paths_pass(path):
    assert hygiene.check_paths([path]) == []


@pytest.mark.parametrize(
    ("label", "sample"),
    [
        ("aws", "AKIA" + "IOSFODNN7EXAMPLE"),
        ("github", "ghp_" + "a" * 36),
        ("openai", "sk-" + "b" * 40),
        ("slack", "xoxb" + "-123456789012-abcdefghijkl"),
        ("private key", "-----BEGIN RSA " + "PRIVATE KEY-----"),
        ("telegram", "123456789:AA" + "c" * 33),
    ],
)
def test_secret_shapes_are_detected(tmp_path, label, sample):
    target = tmp_path / "leak.txt"
    target.write_text(f"token = {sample}\n", encoding="utf-8")
    assert hygiene.check_secrets(["leak.txt"], tmp_path)


def test_ordinary_content_is_not_flagged(tmp_path):
    target = tmp_path / "fine.md"
    target.write_text("The grader threshold is 0.85 and the seed is 20260901.\n", encoding="utf-8")
    assert hygiene.check_secrets(["fine.md"], tmp_path) == []


def test_a_gitignore_missing_a_required_entry_is_reported(tmp_path):
    (tmp_path / ".gitignore").write_text("private/\n.env\n", encoding="utf-8")
    problems = hygiene.check_gitignore(tmp_path)
    assert any(".local_data/" in problem for problem in problems)


@pytest.mark.parametrize(
    ("label", "sample"),
    [
        ("anthropic", "sk-ant-" + "d" * 24),
        ("google", "AIza" + "e" * 35),
        ("jwt", "eyJ" + "f" * 12 + ".eyJ" + "g" * 12 + "." + "h" * 12),
        ("aws secret", 'aws_secret_access_key = "' + "i" * 40 + '"'),
        ("phone", "escribeme al +58 412 555 0134"),
    ],
)
def test_further_secret_shapes_are_detected(label, sample):
    assert hygiene.scan_text("leak.txt", f"value = {sample}\n")


def test_a_real_account_id_in_an_arn_is_reported():
    arn = "arn:aws:iam::" + "987654321098" + ":role/repaso-agentcore-runtime"
    assert hygiene.scan_text("policy.json", arn)


@pytest.mark.parametrize("placeholder", sorted(hygiene.PLACEHOLDER_ACCOUNTS))
def test_documented_placeholder_account_ids_are_allowed(placeholder):
    arn = "arn:aws:iam::" + placeholder + ":role/repaso-agentcore-runtime"
    assert hygiene.scan_text("policy.json", arn) == []


def test_history_is_walked_and_reaches_more_than_the_working_tree():
    blobs = hygiene.history_blobs()
    paths = {path for _, path in blobs}
    assert len(blobs) > len(hygiene.tracked_files())
    assert any(path.startswith("docs/devlog/") for path in paths)


def test_a_file_deleted_from_the_tree_is_still_read_from_history():
    paths = {path for _, path in hygiene.history_blobs()}
    assert "docs/devlog/README.md" in paths
    assert "docs/devlog/README.md" not in hygiene.tracked_files()


def test_every_historical_blob_on_this_branch_is_clean():
    assert hygiene.check_history() == []


def test_the_branch_scope_does_not_depend_on_unrelated_refs():
    branch = {sha for sha, _ in hygiene.history_blobs()}
    every = {sha for sha, _ in hygiene.history_blobs(every_ref=True)}
    assert branch <= every
