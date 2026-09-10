import ast
from pathlib import Path

import repaso.agents as agents_package

VERSION_ARGUMENT = 5
VERSION_KEYWORD = "prompt_version"


def undeclared_calls() -> list[str]:
    silent: list[str] = []
    for path in sorted(Path(agents_package.__file__).parent.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id != "structured":
                continue
            declared = len(node.args) >= VERSION_ARGUMENT or any(
                keyword.arg == VERSION_KEYWORD for keyword in node.keywords
            )
            if not declared:
                silent.append(f"{path.name}:{node.lineno}")
    return silent


def test_every_model_call_says_which_prompt_wrote_it():
    assert undeclared_calls() == []
