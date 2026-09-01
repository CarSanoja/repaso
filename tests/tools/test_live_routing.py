import pytest

from repaso.config.models import DEFAULT_MODELS, FALLBACK_MODELS, ModelRole
from repaso.config.pricing import PRICES
from repaso.config.settings import Settings
from repaso.tools.llm import LocalPlaybackModel, PlaybackExhausted
from tests.live.routing import (
    PING_PROMPT,
    LiveModeRequired,
    build_route_model,
    build_routes,
    ping,
    routing_model_ids,
)


def test_every_role_has_a_default_route():
    defaults = {route.role: route.model_id for route in build_routes() if not route.fallback}
    assert defaults == dict(DEFAULT_MODELS)


def test_every_declared_fallback_is_routed():
    routed: dict[ModelRole, tuple[str, ...]] = {}
    for route in build_routes():
        if route.fallback:
            routed[route.role] = (*routed.get(route.role, ()), route.model_id)
    assert routed == dict(FALLBACK_MODELS)


def test_route_names_are_unique_so_parametrised_cases_do_not_collide():
    names = [route.name for route in build_routes()]
    assert len(set(names)) == len(names)


def test_every_routed_model_is_priced():
    assert set(routing_model_ids()) <= set(PRICES)


def test_routing_ids_line_up_with_the_routes_the_tier_will_call():
    assert routing_model_ids() == tuple(route.model_id for route in build_routes())


async def test_ping_returns_the_text_the_model_streamed():
    model = LocalPlaybackModel(["listo"])
    assert await ping(model) == "listo"


async def test_ping_sends_a_single_short_prompt():
    model = LocalPlaybackModel(["listo"])
    await ping(model)
    assert model.calls == [{"kind": "stream", "system_prompt": None, "message_count": 1}]
    assert len(PING_PROMPT) < 80


async def test_ping_surfaces_a_model_that_will_not_answer():
    with pytest.raises(PlaybackExhausted):
        await ping(LocalPlaybackModel())


def test_local_settings_cannot_stand_in_for_a_routed_model(settings: Settings):
    with pytest.raises(LiveModeRequired, match=build_routes()[0].name):
        build_route_model(build_routes()[0], settings)
