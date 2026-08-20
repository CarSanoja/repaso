import json

import pytest

from repaso.tools.alarms import (
    AlarmScheduler,
    AlarmSpec,
    LocalAlarmScheduler,
    SchedulerAlarms,
    build_alarm_scheduler,
    daily_cron,
)


def make_spec(**overrides) -> AlarmSpec:
    defaults = dict(name="family-1-practice", cron=daily_cron(18, 30))
    defaults.update(overrides)
    return AlarmSpec(**defaults)


def test_daily_cron_uses_eventbridge_field_order():
    assert daily_cron(18, 5) == "cron(5 18 * * ? *)"
    assert daily_cron(0, 0) == "cron(0 0 * * ? *)"


@pytest.mark.parametrize("hour,minute", [(24, 0), (-1, 0), (0, 60), (0, -1)])
def test_daily_cron_rejects_out_of_range_clock(hour, minute):
    with pytest.raises(ValueError):
        daily_cron(hour, minute)


def test_upsert_then_list_returns_the_stored_alarm(settings):
    scheduler = LocalAlarmScheduler(settings)
    spec = make_spec(payload={"family_id": "f1"})
    scheduler.upsert(spec)
    assert scheduler.list_alarms() == [spec]


def test_upsert_replaces_an_alarm_with_the_same_name(settings):
    scheduler = LocalAlarmScheduler(settings)
    scheduler.upsert(make_spec())
    scheduler.upsert(make_spec(cron=daily_cron(7, 0), payload={"mode": "exam"}))
    stored = scheduler.list_alarms()
    assert len(stored) == 1
    assert stored[0].cron == "cron(0 7 * * ? *)"
    assert stored[0].payload == {"mode": "exam"}


def test_list_alarms_is_ordered_by_name(settings):
    scheduler = LocalAlarmScheduler(settings)
    for name in ("zulia", "anzoategui", "merida"):
        scheduler.upsert(make_spec(name=name))
    assert [spec.name for spec in scheduler.list_alarms()] == ["anzoategui", "merida", "zulia"]


def test_remove_deletes_only_the_named_alarm(settings):
    scheduler = LocalAlarmScheduler(settings)
    scheduler.upsert(make_spec(name="keep"))
    scheduler.upsert(make_spec(name="drop"))
    scheduler.remove("drop")
    assert [spec.name for spec in scheduler.list_alarms()] == ["keep"]


def test_remove_is_silent_for_an_unknown_alarm(settings):
    scheduler = LocalAlarmScheduler(settings)
    scheduler.remove("never-created")
    assert scheduler.list_alarms() == []


def test_set_enabled_toggles_state_without_touching_the_cron(settings):
    scheduler = LocalAlarmScheduler(settings)
    scheduler.upsert(make_spec(payload={"family_id": "f1"}))
    scheduler.set_enabled("family-1-practice", False)
    paused = scheduler.list_alarms()[0]
    assert paused.enabled is False
    assert paused.cron == daily_cron(18, 30)
    assert paused.payload == {"family_id": "f1"}
    scheduler.set_enabled("family-1-practice", True)
    assert scheduler.list_alarms()[0].enabled is True


def test_set_enabled_rejects_an_unknown_alarm(settings):
    scheduler = LocalAlarmScheduler(settings)
    with pytest.raises(KeyError):
        scheduler.set_enabled("never-created", False)


def test_alarms_persist_across_scheduler_instances(settings):
    LocalAlarmScheduler(settings).upsert(make_spec(payload={"family_id": "f1"}))
    LocalAlarmScheduler(settings).set_enabled("family-1-practice", False)
    reloaded = LocalAlarmScheduler(settings).list_alarms()
    assert reloaded == [make_spec(enabled=False, payload={"family_id": "f1"})]


def test_reschedule_to_exam_time_keeps_a_single_alarm(settings):
    scheduler = LocalAlarmScheduler(settings)
    scheduler.upsert(make_spec())
    scheduler.upsert(make_spec(cron=daily_cron(5, 45), payload={"mode": "exam"}))
    assert [spec.cron for spec in scheduler.list_alarms()] == ["cron(45 5 * * ? *)"]


def test_store_lands_in_local_data_dir_without_leftover_temp_files(settings):
    scheduler = LocalAlarmScheduler(settings)
    scheduler.upsert(make_spec())
    store = settings.local_data_dir / "alarms.json"
    assert json.loads(store.read_text(encoding="utf-8"))["family-1-practice"]["enabled"] is True
    assert list(settings.local_data_dir.glob("*.tmp")) == []


def test_alarm_spec_is_frozen_and_strict():
    spec = make_spec()
    with pytest.raises(ValueError):
        AlarmSpec(name="x", cron="cron(0 0 * * ? *)", unexpected=True)
    with pytest.raises(ValueError):
        spec.enabled = False


def test_factory_returns_the_local_scheduler_in_local_mode(settings):
    scheduler = build_alarm_scheduler(settings)
    assert isinstance(scheduler, LocalAlarmScheduler)
    assert isinstance(scheduler, AlarmScheduler)
    scheduler.upsert(make_spec())
    assert LocalAlarmScheduler(settings).list_alarms() == [make_spec()]


def test_factory_ignores_cloud_arns_in_local_mode(settings):
    scheduler = build_alarm_scheduler(settings, target_arn="arn:aws:events:::bus/x", role_arn="r")
    assert isinstance(scheduler, LocalAlarmScheduler)


def test_cloud_scheduler_request_is_built_without_touching_aws(settings):
    scheduler = SchedulerAlarms(settings, target_arn="arn:aws:events:::bus/x", role_arn="role")
    assert isinstance(scheduler, AlarmScheduler)
    request = scheduler._request(make_spec(enabled=False, payload={"family_id": "f1"}))
    assert request["FlexibleTimeWindow"] == {"Mode": "OFF"}
    assert request["State"] == "DISABLED"
    assert request["GroupName"] == settings.scheduler_group
    assert request["Target"]["Arn"] == "arn:aws:events:::bus/x"
    assert request["Target"]["RoleArn"] == "role"
    assert json.loads(request["Target"]["Input"]) == {"family_id": "f1"}
