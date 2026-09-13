import sys
from pathlib import Path

import pytest

pytest.importorskip("aws_cdk")

INFRA = str(Path(__file__).resolve().parents[2] / "infra")
if INFRA not in sys.path:
    sys.path.insert(0, INFRA)

from stacks import guardrails_stack  # noqa: E402


def test_the_digest_is_stable_while_the_policy_is():
    assert guardrails_stack.policy_digest() == guardrails_stack.policy_digest()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("HARM_FILTERS", ("HATE",)),
        ("PII_ENTITIES", ("NAME",)),
        ("PII_DIRECTIONS", ("output",)),
        ("BLOCKED_INPUT", "otra cosa"),
        ("BLOCKED_OUTPUT", "otra cosa"),
        ("HIGH", "MEDIUM"),
    ],
)
def test_the_digest_moves_when_the_policy_moves(monkeypatch, name, value):
    before = guardrails_stack.policy_digest()
    monkeypatch.setattr(guardrails_stack, name, value)

    assert guardrails_stack.policy_digest() != before
