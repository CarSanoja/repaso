import pytest

from tests.live.routing import build_route_model, build_routes, ping

ROUTES = build_routes()
ROUTE_IDS = tuple(route.name for route in ROUTES)


@pytest.mark.parametrize("route", ROUTES, ids=ROUTE_IDS)
async def test_the_routed_model_answers(route, live_settings):
    answer = await ping(build_route_model(route, live_settings))
    assert answer, f"{route.name} returned no text"
