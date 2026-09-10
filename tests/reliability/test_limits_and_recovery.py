from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from types import SimpleNamespace

import boto3
import pytest
from botocore.exceptions import ClientError
from pydantic import BaseModel

from repaso.config.models import ModelRole
from repaso.core.orchestration.answer_outcome import record_answer_outcome
from repaso.core.orchestration.quarantine_resolution import resolve_quarantine
from repaso.core.telemetry.context import invocation_context
from repaso.core.telemetry.sink import CloudWatchTelemetrySink, LocalTelemetrySink
from repaso.runtime import invoke_async
from repaso.runtime.recovery import recover_pending
from repaso.tools.instrumented_model import InstrumentedModel
from repaso.tools.llm import LocalPlaybackModel
from repaso.tools.model_limits import ModelLimitReached, ModelLimits
from tests.orchestration.fixtures import FRACTIONS, seed_family, seed_held_answer, seed_open_item
from tests.orchestration.test_gap_recovery import IntermittentSender, make_services, seed_mcqs
from tests.tools.test_cloud_recovery import cloud_services as cloud_services


@pytest.mark.parametrize("backend", ["local", "dynamo"])
def test_family_and_global_budgets_are_atomic(cloud_services, settings, backend):
    s = make_services(settings) if backend == "local" else cloud_services[0]
    day = "2026-09-06"
    with ThreadPoolExecutor(max_workers=4) as pool:
        grants = list(pool.map(lambda _: s.store.reserve_budget("f1", day, 3, 5), range(20)))
    assert sum(grants) == 3
    assert sum(s.store.reserve_budget("f2", day, 3, 5) for _ in range(5)) == 2
    assert not s.store.reserve_budget("f3", day, 3, 5)
    assert s.store.reserve_budget("f1", "2026-09-07", 3, 5)


@pytest.mark.parametrize("backend", ["local", "dynamo"])
def test_concurrent_distinct_answers_preserve_all_learning(cloud_services, settings, backend):
    s = make_services(settings) if backend == "local" else cloud_services[0]
    family, student = seed_family(s.store)
    seed_mcqs(s, family.id)
    item = s.store.list_family_items(family.id)[0]

    def write(number):
        record_answer_outcome(
            s, student.id, item, number % 2 == 0, 45, outcome_id=f"answer-{number}"
        )

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(write, range(8)))
    state = s.store.get_mastery(student.id, FRACTIONS)
    assert state.attempts == 8 and state.correct == 4
    write(0)
    assert s.store.get_mastery(student.id, FRACTIONS).attempts == 8


async def test_failed_work_is_recovered_at_daily_close_without_a_second_user_answer(settings):
    s = make_services(settings)
    family, student = seed_family(s.store)
    seed_mcqs(s, family.id)
    s.sender = IntermittentSender(1)
    event = {
        "kind": "daily_session_due",
        "family_id": family.id,
        "idempotency_key": "scheduled-1",
        "payload": {"student_id": student.id},
    }
    first = await invoke_async(event, s)
    assert first["ok"] is False
    before = len(s.models[ModelRole.GENERATE].calls)
    assert await recover_pending(s) == {"attempted": 1, "recovered": 1}
    assert len(s.models[ModelRole.GENERATE].calls) == before
    assert await recover_pending(s) == {"attempted": 0, "recovered": 0}


class Verdict(BaseModel):
    ok: bool


class TokenModel(LocalPlaybackModel):
    evidence_origin = "live"

    async def structured_output(self, *args, **kwargs):
        yield {"event": {"metadata": {"usage": {"inputTokens": 100, "outputTokens": 20}}}}
        yield {"output": Verdict(ok=True)}


async def test_tokens_origin_and_cloudwatch_metrics_follow_the_real_trace_path(
    settings, monkeypatch
):
    s = make_services(settings)
    mirror = LocalTelemetrySink(settings.local_data_dir / "measured.jsonl", s.clock)
    sink = CloudWatchTelemetrySink("repaso", mirror)
    metrics = []
    monkeypatch.setattr(
        boto3,
        "client",
        lambda *a, **kw: SimpleNamespace(
            put_metric_data=lambda **v: metrics.extend(v["MetricData"])
        ),
    )
    model = TokenModel()
    model.update_config(model_id="us.amazon.nova-micro-v1:0")
    async for _ in InstrumentedModel(model, "judge", sink).structured_output(Verdict, []):
        pass
    trace = mirror.events[-1]
    assert trace.extra["evidence_origin"] == "live"
    assert trace.extra["input_tokens"] == "100" and trace.extra["output_tokens"] == "20"
    assert float(trace.extra["estimated_usd"]) > 0
    assert {m["MetricName"] for m in metrics} >= {
        "llm.input_tokens",
        "llm.output_tokens",
        "llm.judge.structured_output.ok",
    }


async def test_budget_denial_does_not_invoke_model_and_is_explained(settings):
    s = make_services(settings)
    limits = ModelLimits(
        settings.model_copy(update={"daily_llm_budget_calls": 1}), s.store, s.clock
    )
    inner = LocalPlaybackModel([{"ok": True}, {"ok": True}])
    model = InstrumentedModel(inner, "judge", s.telemetry, limits)
    token = invocation_context.set({"family_id": "f1"})
    try:
        async for _ in model.structured_output(Verdict, []):
            pass
        with pytest.raises(ModelLimitReached):
            async for _ in model.structured_output(Verdict, []):
                pass
        assert len(inner.calls) == 1
        s.clock.advance(days=1)
        async for _ in model.structured_output(Verdict, []):
            pass
        assert len(inner.calls) == 2
    finally:
        invocation_context.reset(token)


async def test_provider_quota_is_not_relabelled_as_bad_school_material(settings):
    s = make_services(settings)

    class Throttled(LocalPlaybackModel):
        async def structured_output(self, *args, **kwargs):
            raise ClientError(
                {"Error": {"Code": "ThrottlingException", "Message": "quota"}}, "Converse"
            )
            yield

    model = InstrumentedModel(Throttled(), "judge", s.telemetry)
    with pytest.raises(ModelLimitReached):
        async for _ in model.structured_output(Verdict, []):
            pass


def test_a_human_review_keeps_the_original_response_day(cloud_services):
    s, _, _ = cloud_services
    family, student = seed_family(s.store)
    seed_open_item(s.store)
    held = seed_held_answer(s.store, family.id, student.id)
    original = held.created_at
    s.clock.advance(days=1)
    resolve_quarantine(s, family, held, False)
    grade = s.grade_log.by_student(student.id)[0]
    assert grade.responded_at == original and grade.graded_at.date() != original.date()


def test_callback_time_is_arrival_time_not_the_age_of_the_bot_message():
    from repaso.channel.telegram.parser import parse_update

    now = datetime(2026, 9, 6, 23, 0, tzinfo=UTC)
    message = parse_update(
        {
            "callback_query": {
                "id": "tap",
                "data": "ans:x:1",
                "message": {"chat": {"id": 123}, "date": 1},
            }
        },
        now=now,
    )
    assert message.received_at == now
