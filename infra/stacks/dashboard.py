import aws_cdk as cdk
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_sqs as sqs
from constructs import Construct

from stacks.spend_alarms import (
    DAILY_CEILING_METRIC,
    HOUR,
    MESSAGE_CEILING_METRIC,
    RATE_LIMITED_METRIC,
    SPEND_METRIC,
    UNKNOWN_CHAT_METRIC,
    metric,
)

PERIOD = cdk.Duration.minutes(5)
FULL_WIDTH = 24
HALF_WIDTH = 12
THIRD_WIDTH = 8


def _depth(queue: sqs.Queue) -> cloudwatch.Metric:
    return queue.metric_approximate_number_of_messages_visible(period=PERIOD)


def _age(queue: sqs.Queue) -> cloudwatch.Metric:
    return queue.metric_approximate_age_of_oldest_message(period=PERIOD, statistic="Maximum")


def build_dashboard(
    scope: Construct,
    name: str,
    api_metric,
    functions: list,
    queues: dict[str, sqs.Queue],
    dlqs: dict[str, sqs.Queue],
    alarms: list[cloudwatch.Alarm],
) -> cloudwatch.Dashboard:
    dashboard = cloudwatch.Dashboard(scope, "Dashboard", dashboard_name=name)
    dashboard.add_widgets(
        cloudwatch.GraphWidget(
            title="Estimated model spend",
            left=[metric(SPEND_METRIC, HOUR, "estimated USD per hour")],
            width=HALF_WIDTH,
        ),
        cloudwatch.GraphWidget(
            title="Refusals",
            left=[
                metric(name, PERIOD, label)
                for name, label in (
                    (DAILY_CEILING_METRIC, "daily ceiling"),
                    (MESSAGE_CEILING_METRIC, "message ceiling"),
                    (RATE_LIMITED_METRIC, "rate limited"),
                    (UNKNOWN_CHAT_METRIC, "unknown chat"),
                )
            ],
            width=HALF_WIDTH,
        ),
    )
    dashboard.add_widgets(
        cloudwatch.GraphWidget(
            title="API requests",
            left=[api_metric(name, "Sum") for name in ("Count", "4xx", "5xx")],
            width=HALF_WIDTH,
        ),
        cloudwatch.GraphWidget(
            title="API latency p95",
            left=[api_metric("Latency", "p95")],
            width=HALF_WIDTH,
        ),
    )
    dashboard.add_widgets(
        cloudwatch.GraphWidget(
            title="Lambda invocations",
            left=[fn.metric_invocations(period=PERIOD) for fn in functions],
            width=THIRD_WIDTH,
        ),
        cloudwatch.GraphWidget(
            title="Lambda errors",
            left=[fn.metric_errors(period=PERIOD) for fn in functions],
            width=THIRD_WIDTH,
        ),
        cloudwatch.GraphWidget(
            title="Lambda duration p95",
            left=[fn.metric_duration(period=PERIOD, statistic="p95") for fn in functions],
            width=THIRD_WIDTH,
        ),
    )
    dashboard.add_widgets(
        cloudwatch.GraphWidget(
            title="Queue depth",
            left=[_depth(queue) for queue in queues.values()],
            width=THIRD_WIDTH,
        ),
        cloudwatch.GraphWidget(
            title="Oldest message age",
            left=[_age(queue) for queue in queues.values()],
            width=THIRD_WIDTH,
        ),
        cloudwatch.GraphWidget(
            title="DLQ depth",
            left=[_depth(dlq) for dlq in dlqs.values()],
            width=THIRD_WIDTH,
        ),
    )
    dashboard.add_widgets(
        cloudwatch.AlarmStatusWidget(title="Alarms", alarms=alarms, width=FULL_WIDTH)
    )
    return dashboard
