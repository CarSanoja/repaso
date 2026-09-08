import aws_cdk as cdk
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as cw_actions
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subscriptions
from aws_cdk import aws_sqs as sqs
from config import DeployConfig
from constructs import Construct

from stacks.api_stack import ApiStack
from stacks.messaging_stack import MessagingStack

PERIOD = cdk.Duration.minutes(5)
API_NAMESPACE = "AWS/ApiGateway"
ERROR_RATE_PCT = 5
THROTTLE_THRESHOLD = 0
DLQ_THRESHOLD = 0
API_5XX_THRESHOLD = 0
EVALUATION_PERIODS = 1


class ObservabilityStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        config: DeployConfig,
        api: ApiStack,
        messaging: MessagingStack,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.config = config
        self.alarms: list[cloudwatch.Alarm] = []

        self.topic = sns.Topic(self, "Alerts", topic_name=config.resource("alerts"))
        if config.alert_email:
            self.topic.add_subscription(subscriptions.EmailSubscription(config.alert_email))
        self.action = cw_actions.SnsAction(self.topic)

        self.queues = {
            "ingest": messaging.ingest_queue,
            "tutor": messaging.tutor_queue,
            "quality": messaging.quality_queue,
        }
        self.dlqs = {
            "ingest": messaging.ingest_dlq,
            "tutor": messaging.tutor_dlq,
            "quality": messaging.quality_dlq,
            "scheduler": messaging.scheduler_dlq,
        }

        for name, dlq in self.dlqs.items():
            self._dlq_alarm(name, dlq)
        for name, function in api.functions.items():
            self._error_rate_alarm(name, function)
            self._throttle_alarm(name, function)
        self._api_5xx_alarm(api)
        self._dashboard(api)

    def _alarm(
        self,
        alarm_id: str,
        parts: tuple[str, ...],
        metric: cloudwatch.IMetric,
        threshold: float,
    ) -> None:
        alarm = cloudwatch.Alarm(
            self,
            alarm_id,
            alarm_name=self.config.resource(*parts),
            metric=metric,
            threshold=threshold,
            evaluation_periods=EVALUATION_PERIODS,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        alarm.add_alarm_action(self.action)
        self.alarms.append(alarm)

    def _dlq_alarm(self, name: str, dlq: sqs.Queue) -> None:
        self._alarm(
            f"{name.capitalize()}DlqAlarm",
            (name, "dlq", "depth"),
            dlq.metric_approximate_number_of_messages_visible(period=PERIOD, statistic="Maximum"),
            DLQ_THRESHOLD,
        )

    def _error_rate_alarm(self, name: str, function: lambda_.Function) -> None:
        self._alarm(
            f"{name.capitalize()}ErrorRateAlarm",
            (name, "error", "rate"),
            cloudwatch.MathExpression(
                expression="100 * errors / invocations",
                using_metrics={
                    "errors": function.metric_errors(period=PERIOD, statistic="Sum"),
                    "invocations": function.metric_invocations(period=PERIOD, statistic="Sum"),
                },
                period=PERIOD,
                label=f"{name} error rate",
            ),
            ERROR_RATE_PCT,
        )

    def _throttle_alarm(self, name: str, function: lambda_.Function) -> None:
        self._alarm(
            f"{name.capitalize()}ThrottleAlarm",
            (name, "throttles"),
            function.metric_throttles(period=PERIOD, statistic="Sum"),
            THROTTLE_THRESHOLD,
        )

    def _api_metric(self, metric_name: str, api: ApiStack, statistic: str) -> cloudwatch.Metric:
        return cloudwatch.Metric(
            namespace=API_NAMESPACE,
            metric_name=metric_name,
            dimensions_map={"ApiId": api.http_api.api_id},
            period=PERIOD,
            statistic=statistic,
        )

    def _api_5xx_alarm(self, api: ApiStack) -> None:
        self._alarm(
            "Api5xxAlarm",
            ("api", "5xx"),
            self._api_metric("5xx", api, "Sum"),
            API_5XX_THRESHOLD,
        )

    def _dashboard(self, api: ApiStack) -> None:
        functions = list(api.functions.values())
        dashboard = cloudwatch.Dashboard(
            self, "Dashboard", dashboard_name=self.config.bare()
        )
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="API requests",
                left=[self._api_metric(name, api, "Sum") for name in ("Count", "4xx", "5xx")],
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="API latency p95",
                left=[self._api_metric("Latency", api, "p95")],
                width=12,
            ),
        )
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Lambda invocations",
                left=[fn.metric_invocations(period=PERIOD) for fn in functions],
                width=8,
            ),
            cloudwatch.GraphWidget(
                title="Lambda errors",
                left=[fn.metric_errors(period=PERIOD) for fn in functions],
                width=8,
            ),
            cloudwatch.GraphWidget(
                title="Lambda duration p95",
                left=[fn.metric_duration(period=PERIOD, statistic="p95") for fn in functions],
                width=8,
            ),
        )
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Queue depth",
                left=[self._depth(queue) for queue in self.queues.values()],
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="DLQ depth",
                left=[self._depth(dlq) for dlq in self.dlqs.values()],
                width=12,
            ),
        )
        dashboard.add_widgets(
            cloudwatch.AlarmStatusWidget(title="Alarms", alarms=self.alarms, width=24)
        )

    @staticmethod
    def _depth(queue: sqs.Queue) -> cloudwatch.Metric:
        return queue.metric_approximate_number_of_messages_visible(period=PERIOD)
