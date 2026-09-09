from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SEARCHED = ("src/repaso", "scripts", "tests/live")
READER = REPO_ROOT / "src/repaso/tools/model_usage.py"

PROVIDER_KEYS = (
    "inputTokens",
    "outputTokens",
    "cacheReadInputTokens",
    "cacheWriteInputTokens",
    "reasoningTokens",
)


def modules_naming_a_provider_key() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for directory in SEARCHED:
        for path in sorted((REPO_ROOT / directory).rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            named = [key for key in PROVIDER_KEYS if key in text]
            if named:
                found[str(path.relative_to(REPO_ROOT))] = named
    return found


def test_one_module_owns_the_wire_names_the_provider_reports_usage_under():
    assert set(modules_naming_a_provider_key()) == {str(READER.relative_to(REPO_ROOT))}


def test_the_reader_still_covers_every_key_it_owns():
    text = READER.read_text(encoding="utf-8")
    assert all(f'"{key}"' in text for key in PROVIDER_KEYS)
