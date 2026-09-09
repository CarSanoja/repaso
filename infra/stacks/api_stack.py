import aws_cdk as cdk
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda_event_sources as sources
from config import DeployConfig
from constructs import Construct

from stacks.api_functions import build_function, environment
from stacks.foundation_stack import FoundationStack
from stacks.messaging_stack import MessagingStack

METRIC_ACTION = "cloudwatch:PutMetricData"
BATCH_SIZE = 5
WEBHOOK_PATH = "/telegram/webhook"
PUBLIC_PATHS = ("/judge", "/judge/{proxy+}", "/health", "/healthz", "/readyz")


class ApiStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        config: DeployConfig,
        foundation: FoundationStack,
        messaging: MessagingStack,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.config = config
        self.foundation = foundation
        self.messaging = messaging

        variables = environment(config, self.region, foundation, messaging)
        self.webhook = self._function(
            "webhook", 512, cdk.Duration.seconds(30), config.webhook_reserved_concurrency, variables
        )
        self.worker = self._function(
            "worker", 1024, cdk.Duration.minutes(10), config.worker_reserved_concurrency, variables
        )
        self.scheduler = self._function(
            "scheduler",
            512,
            cdk.Duration.minutes(1),
            config.scheduler_reserved_concurrency,
            variables,
            messaging.scheduler_dlq,
        )
        self.functions = {
            "webhook": self.webhook,
            "worker": self.worker,
            "scheduler": self.scheduler,
        }

        self._wire_webhook()
        self._wire_worker()
        self._wire_scheduler()
        events.Rule(
            self,
            "DailyCloseTimer",
            schedule=events.Schedule.cron(hour="3", minute="50"),
            targets=[
                targets.LambdaFunction(
                    self.scheduler,
                    event=events.RuleTargetInput.from_object({"kind": "daily_close"}),
                )
            ],
        )
        self.http_api = self._http_api()

    def _function(self, name, memory, timeout, reserved, variables, dead_letter_queue=None):
        return build_function(
            self, self.config, name, memory, timeout, reserved, variables, dead_letter_queue
        )

    def _metric_statement(self) -> iam.PolicyStatement:
        return iam.PolicyStatement(
            actions=[METRIC_ACTION],
            resources=["*"],
            conditions={"StringEquals": {"cloudwatch:namespace": self.config.bare()}},
        )

    def _wire_webhook(self) -> None:
        self.webhook.add_to_role_policy(self._metric_statement())
        self.foundation.table.grant_read_write_data(self.webhook)
        self.foundation.telegram_secret.grant_read(self.webhook)
        self.foundation.judge_secret.grant_read(self.webhook)
        self.messaging.bus.grant_put_events_to(self.webhook)

    def _wire_worker(self) -> None:
        self.worker.add_to_role_policy(self._metric_statement())
        self.worker.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock-agentcore:InvokeAgentRuntime"],
                resources=[
                    f"arn:{self.partition}:bedrock-agentcore:{self.region}:"
                    f"{self.account}:runtime/{self.config.bare()}*"
                ],
            )
        )
        self.worker.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[
                    f"arn:{self.partition}:ssm:{self.region}:{self.account}:"
                    f"parameter/{self.config.bare()}/agentcore/runtime-arn"
                ],
            )
        )
        for queue in (
            self.messaging.ingest_queue,
            self.messaging.tutor_queue,
            self.messaging.quality_queue,
        ):
            self.worker.add_event_source(
                sources.SqsEventSource(
                    queue,
                    batch_size=BATCH_SIZE,
                    max_concurrency=self.config.worker_queue_concurrency,
                    report_batch_item_failures=True,
                )
            )

    def _wire_scheduler(self) -> None:
        self.scheduler.add_to_role_policy(self._metric_statement())
        self.foundation.table.grant_read_write_data(self.scheduler)
        self.messaging.bus.grant_put_events_to(self.scheduler)
        invoker = iam.Role.from_role_arn(
            self,
            "SchedulerInvokeRole",
            self.messaging.scheduler_role.role_arn,
            mutable=True,
        )
        self.scheduler.grant_invoke(invoker)

    def _http_api(self) -> apigwv2.HttpApi:
        integration = integrations.HttpLambdaIntegration("WebhookIntegration", self.webhook)
        http_api = apigwv2.HttpApi(self, "HttpApi", api_name=self.config.resource("api"))
        http_api.add_routes(
            path=WEBHOOK_PATH,
            methods=[apigwv2.HttpMethod.POST],
            integration=integration,
        )
        for path in PUBLIC_PATHS:
            http_api.add_routes(
                path=path,
                methods=[apigwv2.HttpMethod.ANY],
                integration=integration,
            )
        self._throttle(http_api)
        cdk.CfnOutput(self, "HttpApiUrl", value=http_api.api_endpoint)
        return http_api

    def _throttle(self, http_api: apigwv2.HttpApi) -> None:
        stage = http_api.default_stage.node.default_child
        stage.default_route_settings = apigwv2.CfnStage.RouteSettingsProperty(
            throttling_rate_limit=self.config.webhook_rate_limit,
            throttling_burst_limit=self.config.webhook_burst_limit,
        )
