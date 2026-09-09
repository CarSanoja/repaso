import pytest

from tests.infra.conftest import ALERT_EMAIL
from tests.infra.fixtures import annotations, properties, resources, template

BUDGET = "AWS::Budgets::Budget"
ALARM = "AWS::CloudWatch::Alarm"
SUBSCRIPTION = "AWS::SNS::Subscription"
FUNCTION = "AWS::Lambda::Function"
MAPPING = "AWS::Lambda::EventSourceMapping"
STAGE = "AWS::ApiGatewayV2::Stage"
QUEUE = "AWS::SQS::Queue"

BUDGET_LIMITS = (25, 40)
COST_FILTER = {"TagKeyValue": ["user:project$repaso"]}
QUEUES = ("ingest", "tutor", "quality")
WORKER_TIMEOUT_SECONDS = 600
VISIBILITY_SECONDS = 900

SPEND_ALARMS = (
    "repaso-model-spend-hour",
    "repaso-model-spend-day",
    "repaso-model-daily-ceiling",
    "repaso-model-message-ceiling",
    "repaso-chats-rate-limited",
    "repaso-chats-unknown-exhausted",
)
STALL_ALARMS = tuple(f"repaso-{name}-queue-stalled" for name in QUEUES)


def alarm_names(assembly) -> set[str]:
    return {entry["AlarmName"] for entry in properties(assembly, "observability", ALARM)}


def by_name(assembly, stack: str, resource_type: str, key: str) -> dict:
    return {entry[key]: entry for entry in properties(assembly, stack, resource_type)}


def test_a_budget_counts_only_what_this_project_tagged(assembly):
    budgets = properties(assembly, "foundation", BUDGET)

    assert {entry["Budget"]["BudgetLimit"]["Amount"] for entry in budgets} == set(BUDGET_LIMITS)
    for entry in budgets:
        assert entry["Budget"]["CostFilters"] == COST_FILTER


def test_a_budget_warns_before_the_money_is_gone_and_not_only_after(assembly):
    for entry in properties(assembly, "foundation", BUDGET):
        raised = {
            (n["Notification"]["NotificationType"], n["Notification"]["Threshold"])
            for n in entry["NotificationsWithSubscribers"]
        }
        assert raised == {
            ("ACTUAL", 50),
            ("ACTUAL", 80),
            ("ACTUAL", 100),
            ("FORECASTED", 100),
        }


def test_every_budget_and_every_alarm_reach_the_same_place(assembly):
    topics = resources(assembly, "foundation", "AWS::SNS::Topic")
    assert len(topics) == 1
    topic = next(iter(topics))

    for entry in properties(assembly, "foundation", BUDGET):
        for notification in entry["NotificationsWithSubscribers"]:
            subscriber = notification["Subscribers"][0]
            assert subscriber["SubscriptionType"] == "SNS"
            assert subscriber["Address"] == {"Ref": topic}
    for entry in properties(assembly, "observability", ALARM):
        assert len(entry["AlarmActions"]) == 1


def test_the_configured_address_is_subscribed_to_that_place(assembly):
    subscriptions = properties(assembly, "foundation", SUBSCRIPTION)

    assert [entry["Endpoint"] for entry in subscriptions] == [ALERT_EMAIL]
    assert [entry["Protocol"] for entry in subscriptions] == ["email"]


def test_budgets_still_exist_when_nobody_has_been_named_yet(unaddressed_assembly):
    assert len(properties(unaddressed_assembly, "foundation", BUDGET)) == len(BUDGET_LIMITS)
    assert properties(unaddressed_assembly, "foundation", SUBSCRIPTION) == []


def test_an_unaddressed_deployment_says_so_out_loud(unaddressed_assembly):
    warnings = [
        entry["data"]
        for entry in annotations(unaddressed_assembly, "foundation")
        if entry["type"] == "aws:cdk:warning"
    ]

    assert any("no subscription" in str(text) for text in warnings)


@pytest.mark.parametrize("name", SPEND_ALARMS + STALL_ALARMS)
def test_the_alarm_a_person_would_act_on_exists(assembly, name):
    assert name in alarm_names(assembly)


def watched(alarms: dict, name: str) -> dict:
    return alarms[name]["Metrics"][0]["MetricStat"]["Metric"]


def test_spend_alarms_read_the_metrics_the_application_publishes(assembly):
    alarms = by_name(assembly, "observability", ALARM, "AlarmName")

    for name in SPEND_ALARMS:
        assert watched(alarms, name)["Namespace"] == "repaso"
    assert watched(alarms, "repaso-model-spend-hour")["MetricName"] == "llm.estimated_usd"
    assert watched(alarms, "repaso-model-daily-ceiling")["MetricName"] == (
        "spend.daily_ceiling.tripped"
    )
    assert watched(alarms, "repaso-chats-unknown-exhausted")["MetricName"] == (
        "throttle.unknown_chat_exhausted.refused"
    )


def test_every_lambda_that_measures_itself_may_publish_the_measurement(assembly):
    statements = [
        statement
        for entry in properties(assembly, "api", "AWS::IAM::Policy")
        for statement in entry["PolicyDocument"]["Statement"]
        if statement["Action"] == "cloudwatch:PutMetricData"
    ]

    assert len(statements) == 3
    for statement in statements:
        assert statement["Condition"] == {"StringEquals": {"cloudwatch:namespace": "repaso"}}


def test_no_lambda_may_scale_without_a_ceiling(assembly):
    functions = by_name(assembly, "api", FUNCTION, "FunctionName")

    for name in ("repaso-webhook", "repaso-worker", "repaso-scheduler"):
        assert functions[name]["ReservedConcurrentExecutions"] > 0


def test_a_queue_burst_cannot_open_unlimited_workers(assembly):
    mappings = properties(assembly, "api", MAPPING)

    assert len(mappings) == len(QUEUES)
    for entry in mappings:
        assert entry["ScalingConfig"]["MaximumConcurrency"] > 0
        assert entry["FunctionResponseTypes"] == ["ReportBatchItemFailures"]


def test_the_public_route_carries_its_own_throttle(assembly):
    stages = properties(assembly, "api", STAGE)

    assert len(stages) == 1
    settings = stages[0]["DefaultRouteSettings"]
    assert settings["ThrottlingRateLimit"] > 0
    assert settings["ThrottlingBurstLimit"] >= settings["ThrottlingRateLimit"]


def test_a_message_cannot_be_redelivered_while_it_is_still_being_worked(assembly):
    queues = by_name(assembly, "messaging", QUEUE, "QueueName")
    worker = by_name(assembly, "api", FUNCTION, "FunctionName")["repaso-worker"]

    assert worker["Timeout"] == WORKER_TIMEOUT_SECONDS
    for name in QUEUES:
        assert queues[f"repaso-{name}"]["VisibilityTimeout"] == VISIBILITY_SECONDS
        assert queues[f"repaso-{name}"]["VisibilityTimeout"] > worker["Timeout"]


def test_a_message_that_always_fails_stops_after_a_bounded_number_of_tries(assembly):
    queues = by_name(assembly, "messaging", QUEUE, "QueueName")

    for name in QUEUES:
        redrive = queues[f"repaso-{name}"]["RedrivePolicy"]
        assert 1 <= redrive["maxReceiveCount"] <= 5
        assert f"repaso-{name}-dlq" in queues
        assert "RedrivePolicy" not in queues[f"repaso-{name}-dlq"]


def test_the_template_still_names_one_dashboard(assembly):
    template(assembly, "observability").resource_count_is("AWS::CloudWatch::Dashboard", 1)
