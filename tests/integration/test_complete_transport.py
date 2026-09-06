"""Production adapters, emulated AWS and explicit remote-model/Telegram boundaries."""

import asyncio
import json
from io import BytesIO
from types import SimpleNamespace

import boto3
import httpx
import pytest

from repaso.api.dependencies import AppContainer
from repaso.api.main import create_app
from repaso.core.orchestration.scheduling import alarm_name
from repaso.lambdas import scheduler, worker
from repaso.runtime import invoke
from repaso.simulator.demo_scenario import (
    build_scenario_services,
    run_demo_scenario,
    scenario_settings,
)
from repaso.simulator.demo_stage import CHAT_REF, Stage
from repaso.simulator.demo_transcript import PARENT
from repaso.tools.alarms import SchedulerAlarms
from repaso.tools.event_bus import EventBridgePublisher
from repaso.tools.telegram import TelegramSender
from tests.tools.test_cloud_recovery import cloud_services as cloud_services


class SimulatedTelegram(TelegramSender):
    def __init__(self, fail_at):
        self.sent, self.attempts, self.fail_at = [], 0, set(fail_at)
        super().__init__(
            "synthetic-token", httpx.Client(transport=httpx.MockTransport(self.accept))
        )

    def accept(self, request):
        self.attempts += 1
        if self.attempts in self.fail_at:
            return httpx.Response(503, json={"ok": False})
        payload = json.loads(request.content)
        assert "parse_mode" not in payload
        keyboard = json.loads(payload.get("reply_markup", '{"inline_keyboard":[]}'))
        buttons = [
            {"label": b["text"], "callback_data": b["callback_data"]}
            for row in keyboard["inline_keyboard"]
            for b in row
        ]
        assert all(1 <= len(b["callback_data"].encode()) <= 64 for b in buttons)
        self.sent.append(
            {"chat_ref": payload["chat_id"], "text": payload["text"], "buttons": buttons}
        )
        return httpx.Response(200, json={"ok": True, "result": {"message_id": len(self.sent)}})


@pytest.mark.parametrize("run_number", range(10))
async def test_ten_complete_transport_journeys(cloud_services, monkeypatch, tmp_path, run_number):
    cloud, _, _ = cloud_services
    settings = scenario_settings(tmp_path / "journey")
    services = build_scenario_services(settings)
    services.store, services.grade_log, services.media = cloud.store, cloud.grade_log, cloud.media
    services.sender = SimulatedTelegram({2, 16, 24} if run_number % 2 else set())
    sqs = boto3.client("sqs", region_name="us-east-1")
    queue = sqs.create_queue(QueueName="repaso-rehearsal")["QueueUrl"]
    arn = sqs.get_queue_attributes(QueueUrl=queue, AttributeNames=["QueueArn"])["Attributes"][
        "QueueArn"
    ]
    events = boto3.client("events", region_name="us-east-1")
    events.create_event_bus(Name="repaso")
    events.put_rule(
        Name="all-repaso", EventBusName="repaso", EventPattern=json.dumps({"source": ["repaso"]})
    )
    events.put_targets(
        Rule="all-repaso", EventBusName="repaso", Targets=[{"Id": "worker", "Arn": arn}]
    )
    alarm_client = boto3.client("scheduler", region_name="us-east-1")
    alarm_client.create_schedule_group(Name="repaso")
    monkeypatch.setattr("repaso.config.clients.scheduler_client", lambda: alarm_client)
    services.alarms = SchedulerAlarms(
        settings,
        "arn:aws:lambda:us-east-1:123456789012:function:repaso-scheduler",
        "arn:aws:iam::123456789012:role/repaso-scheduler",
    )
    stages = []
    calls, results, recovered = [], [], []
    failure = [run_number % 2 == 1]

    def publish(**kwargs):
        if failure[0]:
            failure[0] = False
            return {"FailedEntryCount": 1, "Entries": [{"ErrorCode": "InternalFailure"}]}
        return events.put_events(**kwargs)

    monkeypatch.setattr(
        "repaso.config.clients.events_client", lambda: SimpleNamespace(put_events=publish)
    )
    services.publisher = EventBridgePublisher("repaso")
    monkeypatch.setattr(scheduler, "store", lambda: services.store)
    monkeypatch.setattr(scheduler, "publisher", lambda: services.publisher)
    monkeypatch.setattr(scheduler, "SystemClock", lambda: services.clock)
    from repaso.config.settings import clear_settings_cache

    monkeypatch.setenv("REPASO_LOCAL_MODE", "false")
    monkeypatch.setenv("REPASO_AWS_REGION", "us-east-1")
    clear_settings_cache()

    def remote(**kwargs):
        assert len(kwargs["runtimeSessionId"]) == 64
        assert kwargs["contentType"] == "application/json"
        body = json.loads(kwargs["payload"])
        calls.append(body)
        result = invoke(body, services)
        results.append(result)
        return {"response": BytesIO(json.dumps(result).encode())}

    def client(name, **kwargs):
        if name == "ssm":
            return SimpleNamespace(
                get_parameter=lambda **kw: {
                    "Parameter": {
                        "Value": "arn:aws:bedrock-agentcore:us-east-1:"
                        "123456789012:runtime/repaso-test"
                    }
                }
            )
        assert name == "bedrock-agentcore"
        return SimpleNamespace(invoke_agent_runtime=remote)

    monkeypatch.setattr(boto3, "Session", lambda **kw: SimpleNamespace(client=client))
    container = AppContainer(
        settings,
        services.store,
        services.sender,
        services.fetcher,
        services.publisher,
        telegram_secret="synthetic-secret",
        clock=services.clock,
    )
    web = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(container)), base_url="http://test"
    )

    class TransportStage(Stage):
        def __init__(self, s):
            super().__init__(s)
            stages.append(self)

        async def dispatch(self, payload):
            if payload["kind"] == "channel_message":
                inbound = payload["payload"]
                base = {
                    "message_id": self._inbound,
                    "chat": {"id": int(inbound["chat_ref"]), "type": "private"},
                    "date": int(self.clock.now().timestamp()),
                }
                if inbound.get("callback_data"):
                    update = {
                        "update_id": self._inbound,
                        "callback_query": {
                            "id": f"tap-{self._inbound}",
                            "message": base,
                            "data": inbound["callback_data"],
                        },
                    }
                else:
                    if inbound.get("text"):
                        base["text"] = inbound["text"]
                    if inbound.get("media"):
                        base["photo"] = [
                            {
                                "file_id": inbound["media"]["media_ref"],
                                "width": 1600,
                                "height": 1200,
                            }
                        ]
                    update = {"update_id": self._inbound, "message": base}
                for _ in range(3):
                    posted = await web.post(
                        "/telegram/webhook",
                        json=update,
                        headers={"X-Telegram-Bot-Api-Secret-Token": "synthetic-secret"},
                    )
                    if posted.status_code == 200:
                        break
                    recovered.append("publication")
                assert posted.status_code == 200
                duplicate = await web.post(
                    "/telegram/webhook",
                    json=update,
                    headers={"X-Telegram-Bot-Api-Secret-Token": "synthetic-secret"},
                )
                assert duplicate.json().get("duplicate") is True
            else:
                assert payload["kind"] == "daily_session_due"
                tick = scheduler.handler({"family_id": payload["family_id"], **payload["payload"]})
                assert tick.get("fired"), tick
            first_result = None
            for _ in range(40):
                messages = sqs.receive_message(
                    QueueUrl=queue, MaxNumberOfMessages=1, VisibilityTimeout=0
                ).get("Messages", [])
                if not messages:
                    break
                message = messages[0]
                record = {"messageId": message["MessageId"], "body": message["Body"]}
                for _attempt in range(3):
                    result = await asyncio.to_thread(worker.handler, {"Records": [record]})
                    if not result["batchItemFailures"]:
                        break
                    recovered.append("runtime/transport")
                assert result == {"batchItemFailures": []}
                first_result = first_result or results[-1]
                before = len(services.sender.sent)
                # Lost SQS ACK: same event reaches the durable runtime again.
                assert await asyncio.to_thread(worker.handler, {"Records": [record]}) == {
                    "batchItemFailures": []
                }
                assert len(services.sender.sent) == before
                sqs.delete_message(QueueUrl=queue, ReceiptHandle=message["ReceiptHandle"])
            assert first_result and first_result["ok"]
            self._replay_outbox()
            return first_result["result"]

    try:
        decision = "reduce_load" if run_number % 2 else "teacher_note"
        result = await run_demo_scenario(settings, services, decision, stage_factory=TransportStage)
        assert result.failures == []
        family = services.store.find_family_by_chat("telegram", CHAT_REF)
        stage = stages[0]
        await stage.says(PARENT, "/pause", text="/pause")
        assert (
            alarm_client.get_schedule(Name=alarm_name(family.id), GroupName="repaso")["State"]
            == "DISABLED"
        )
        await stage.says(PARENT, "/resume", text="/resume")
        assert (
            alarm_client.get_schedule(Name=alarm_name(family.id), GroupName="repaso")["State"]
            == "ENABLED"
        )
        await stage.says(PARENT, "Erase my data", callback="forget:yes")
        assert services.store.get_family(family.id) is None
        assert services.store.list_records(family.id) == []
        assert services.alarms.list_alarms() == []
        assert len(calls) >= 40
        assert any(c["kind"] == "escalation_resolved" for c in calls)
        assert any(c["kind"] == "quarantine_resolved" for c in calls)
        if run_number % 2:
            assert "publication" in recovered and recovered.count("runtime/transport") == 3
    finally:
        await web.aclose()
