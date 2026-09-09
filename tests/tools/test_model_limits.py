import pytest
from pydantic import BaseModel

from repaso.config.models import ModelRole
from repaso.core.telemetry.context import invocation_context
from repaso.tools.call_quota import build_call_quota
from repaso.tools.instrumented_model import InstrumentedModel
from repaso.tools.llm import LocalPlaybackModel
from repaso.tools.model_limits import (
    MESSAGE_SCOPE_KEY,
    LimitReason,
    ModelLimitReached,
    ModelLimits,
)
from tests.orchestration.fixtures import make_services

MESSAGE = "9b2f4c1ad0e7"
OTHER_MESSAGE = "5518cc90ab34"


class Verdict(BaseModel):
    ok: bool


def bounded(settings, calls: int = 3):
    services = make_services(settings.model_copy(update={"message_llm_budget_calls": calls}))
    limits = ModelLimits(
        services.settings, services.store, services.clock, build_call_quota(services.settings)
    )
    inner = LocalPlaybackModel([{"ok": True} for _ in range(20)])
    role = ModelRole.JUDGE.value
    return services, inner, InstrumentedModel(inner, role, services.telemetry, limits)


async def drive(model, times: int) -> int:
    reached = 0
    for _ in range(times):
        try:
            async for _event in model.structured_output(Verdict, []):
                pass
        except ModelLimitReached as error:
            assert error.reason is LimitReason.MESSAGE_CEILING
            reached += 1
    return reached


async def test_one_message_spends_its_allowance_and_no_more(settings):
    _, inner, model = bounded(settings)

    token = invocation_context.set({"family_id": "f1", MESSAGE_SCOPE_KEY: MESSAGE})
    try:
        denied = await drive(model, 7)
    finally:
        invocation_context.reset(token)

    assert len(inner.calls) == 3
    assert denied == 4


async def test_the_next_message_from_the_same_family_starts_fresh(settings):
    _, inner, model = bounded(settings)

    for scope in (MESSAGE, OTHER_MESSAGE):
        token = invocation_context.set({"family_id": "f1", MESSAGE_SCOPE_KEY: scope})
        try:
            await drive(model, 3)
        finally:
            invocation_context.reset(token)

    assert len(inner.calls) == 6


async def test_a_spent_message_stays_spent_across_a_cold_start(settings):
    services, inner, model = bounded(settings)

    token = invocation_context.set({"family_id": "f1", MESSAGE_SCOPE_KEY: MESSAGE})
    try:
        await drive(model, 3)
        restarted = ModelLimits(
            services.settings,
            services.store,
            services.clock,
            build_call_quota(services.settings),
        )
        after = InstrumentedModel(inner, ModelRole.JUDGE.value, services.telemetry, restarted)
        assert await drive(after, 2) == 2
    finally:
        invocation_context.reset(token)

    assert len(inner.calls) == 3


async def test_cohort_wide_work_carries_no_per_message_ceiling(settings):
    _, inner, model = bounded(settings)

    token = invocation_context.set({"family_id": "system"})
    try:
        assert await drive(model, 6) == 0
    finally:
        invocation_context.reset(token)

    assert len(inner.calls) == 6


async def test_a_denied_message_does_not_spend_the_family_day(settings):
    services, _, model = bounded(settings)
    day = services.clock.today().isoformat()

    token = invocation_context.set({"family_id": "f1", MESSAGE_SCOPE_KEY: MESSAGE})
    try:
        await drive(model, 9)
    finally:
        invocation_context.reset(token)

    assert services.store.reserve_budget("f1", day, 4, 400)
    assert not services.store.reserve_budget("f1", day, 4, 400)


async def test_the_daily_ceiling_still_reports_itself_as_the_daily_one(settings):
    services, _, model = bounded(settings, calls=99)
    services.settings = services.settings.model_copy(update={"daily_llm_budget_calls": 1})
    model._limits.settings = services.settings

    token = invocation_context.set({"family_id": "f1", MESSAGE_SCOPE_KEY: MESSAGE})
    try:
        async for _event in model.structured_output(Verdict, []):
            pass
        with pytest.raises(ModelLimitReached) as raised:
            async for _event in model.structured_output(Verdict, []):
                pass
    finally:
        invocation_context.reset(token)

    assert raised.value.reason is LimitReason.DAILY_CEILING
