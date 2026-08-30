import re
from pathlib import Path

import repaso
from repaso.runtime.handlers import HANDLERS
from repaso.schemas.events import EventKind

MESSAGING_STACK = Path(__file__).resolve().parents[2] / "infra/stacks/messaging_stack.py"
CHANNEL_RUNNER = Path(repaso.__path__[0]) / "core/orchestration/channel_runner.py"
RENDERED_CALLBACK = re.compile(r'callback_data=f"([a-z_]+:)')
ROUTED_PREFIX = re.compile(r'^[A-Z_]+_PREFIX = "([a-z_]+:)"$', re.MULTILINE)


def routed_detail_types() -> set[str]:
    return set(re.findall(r'"([a-z_]+)"', MESSAGING_STACK.read_text(encoding="utf-8")))


def rendered_callback_prefixes() -> set[str]:
    return {
        prefix
        for path in Path(repaso.__path__[0]).rglob("*.py")
        for prefix in RENDERED_CALLBACK.findall(path.read_text(encoding="utf-8"))
    }


def routed_callback_prefixes() -> set[str]:
    return set(ROUTED_PREFIX.findall(CHANNEL_RUNNER.read_text(encoding="utf-8")))


def test_every_event_kind_has_a_runtime_handler():
    assert set(HANDLERS) == set(EventKind)


def test_every_event_kind_is_delivered_by_a_rule():
    unrouted = {kind.value for kind in EventKind} - routed_detail_types()
    assert not unrouted, f"published but never delivered in AWS: {sorted(unrouted)}"


def test_every_button_the_tutor_renders_is_routed_back():
    rendered = rendered_callback_prefixes()
    assert rendered, "no callback buttons were found to check"
    unrouted = rendered - routed_callback_prefixes()
    assert not unrouted, f"shown to the parent but tapped into nothing: {sorted(unrouted)}"
