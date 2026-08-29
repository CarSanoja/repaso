import re
from pathlib import Path

from repaso.runtime.handlers import HANDLERS
from repaso.schemas.events import EventKind

MESSAGING_STACK = Path(__file__).resolve().parents[2] / "infra/stacks/messaging_stack.py"


def routed_detail_types() -> set[str]:
    return set(re.findall(r'"([a-z_]+)"', MESSAGING_STACK.read_text(encoding="utf-8")))


def test_every_event_kind_has_a_runtime_handler():
    assert set(HANDLERS) == set(EventKind)


def test_every_event_kind_is_delivered_by_a_rule():
    unrouted = {kind.value for kind in EventKind} - routed_detail_types()
    assert not unrouted, f"published but never delivered in AWS: {sorted(unrouted)}"
