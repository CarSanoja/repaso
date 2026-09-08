from pathlib import Path

import aws_cdk as cdk
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as sources
from aws_cdk import aws_logs as logs
from aws_cdk import aws_sqs as sqs
from config import DeployConfig
from constructs import Construct

from stacks.foundation_stack import FoundationStack
from stacks.messaging_stack import MessagingStack

REPO_ROOT = str(Path(__file__).resolve().parents[2])
BEDROCK_ACTIONS = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
BATCH_SIZE = 5

RETENTION = {
    1: logs.RetentionDays.ONE_DAY,
    3: logs.RetentionDays.THREE_DAYS,
    5: logs.RetentionDays.FIVE_DAYS,
    7: logs.RetentionDays.ONE_WEEK,
    14: logs.RetentionDays.TWO_WEEKS,
    30: logs.RetentionDays.ONE_MONTH,
    60: logs.RetentionDays.TWO_MONTHS,
    90: logs.RetentionDays.THREE_MONTHS,
    180: logs.RetentionDays.SIX_MONTHS,
    365: logs.RetentionDays.ONE_YEAR,
}


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

        self.webhook = self._function("webhook", memory=512, timeout=cdk.Duration.seconds(30))
        self.worker = self._function(
            "worker",
            memory=1024,
            timeout=cdk.Duration.minutes(10),
        )
        self.scheduler = self._function(
            "scheduler",
            memory=512,
            timeout=cdk.Duration.minutes(1),
            dead_letter_queue=messaging.scheduler_dlq,
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

    def _function(
        self,
        name: str,
        memory: int,
        timeout: cdk.Duration,
        dead_letter_queue: sqs.Queue | None = None,
    ) -> lambda_.Function:
        resource_name = self.config.resource(name)
        log_group = logs.LogGroup(
            self,
            f"{name.capitalize()}Logs",
            log_group_name=f"/aws/lambda/{resource_name}",
            retention=RETENTION.get(self.config.log_retention_days, logs.RetentionDays.ONE_MONTH),
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )
        return lambda_.DockerImageFunction(
            self,
            f"{name.capitalize()}Function",
            function_name=resource_name,
            architecture=lambda_.Architecture.ARM_64,
            code=lambda_.DockerImageCode.from_image_asset(
                REPO_ROOT,
                file="deploy/lambda/Dockerfile",
                cmd=[f"repaso.lambdas.{name}.handler"],
                exclude=[
                    "*",
                    "!pyproject.toml",
                    "!requirements.lock",
                    "!README.md",
                    "!LICENSE",
                    "!src",
                    "!deploy/lambda/Dockerfile",
                    "**/__pycache__",
                    "**/*.pyc",
                    "**/*.egg-info",
                ],
                ignore_mode=cdk.IgnoreMode.DOCKER,
            ),
            memory_size=memory,
            timeout=timeout,
            environment=self._environment(),
            log_group=log_group,
            dead_letter_queue=dead_letter_queue,
            dead_letter_queue_enabled=dead_letter_queue is not None,
        )

    def _environment(self) -> dict[str, str]:
        config = self.config
        return {
            "REPASO_AWS_REGION": self.region,
            "REPASO_DDB_TABLE": self.foundation.table.table_name,
            "REPASO_MEDIA_BUCKET": self.foundation.media_bucket.bucket_name,
            "REPASO_CURRICULUM_BUCKET": self.foundation.curriculum_bucket.bucket_name,
            "REPASO_EVENT_BUS": self.messaging.bus.event_bus_name,
            "REPASO_SCHEDULER_GROUP": config.bare(),
            "REPASO_LOCAL_DATA_DIR": "/tmp/repaso",
            "REPASO_CURRICULUM_SOURCE": "bundled",
            "REPASO_AGENTCORE_RUNTIME_ARN_PARAMETER": config.parameter("agentcore", "runtime-arn"),
            "REPASO_TELEGRAM_SECRET_NAME": config.secret("telegram"),
            "REPASO_JUDGE_CODE_SECRET_NAME": config.secret("judge"),
            "REPASO_INVITE_CODES_SECRET_NAME": config.secret("pilot-invite-codes"),
        }

    def _bedrock_statement(self) -> iam.PolicyStatement:
        return iam.PolicyStatement(
            actions=BEDROCK_ACTIONS,
            resources=[
                f"arn:{self.partition}:bedrock:*::foundation-model/*",
                f"arn:{self.partition}:bedrock:{self.region}:{self.account}:inference-profile/*",
            ],
        )

    def _wire_webhook(self) -> None:
        self.foundation.table.grant_read_write_data(self.webhook)
        self.foundation.media_bucket.grant_read_write(self.webhook)
        self.foundation.telegram_secret.grant_read(self.webhook)
        self.foundation.judge_secret.grant_read(self.webhook)
        self.messaging.bus.grant_put_events_to(self.webhook)

    def _wire_worker(self) -> None:
        self.foundation.table.grant_read_write_data(self.worker)
        self.foundation.media_bucket.grant_read_write(self.worker)
        self.foundation.curriculum_bucket.grant_read(self.worker)
        self.foundation.telegram_secret.grant_read(self.worker)
        self.foundation.judge_secret.grant_read(self.worker)
        self.foundation.invite_codes_secret.grant_read(self.worker)
        self.messaging.bus.grant_put_events_to(self.worker)
        self.worker.add_to_role_policy(self._bedrock_statement())
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
                    report_batch_item_failures=True,
                )
            )

    def _wire_scheduler(self) -> None:
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
            path="/telegram/webhook",
            methods=[apigwv2.HttpMethod.POST],
            integration=integration,
        )
        for path in ("/judge", "/judge/{proxy+}", "/health", "/healthz", "/readyz"):
            http_api.add_routes(
                path=path,
                methods=[apigwv2.HttpMethod.ANY],
                integration=integration,
            )
        cdk.CfnOutput(self, "HttpApiUrl", value=http_api.api_endpoint)
        return http_api
