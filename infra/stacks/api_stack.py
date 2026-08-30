from pathlib import Path

import aws_cdk as cdk
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as sources
from aws_cdk import aws_logs as logs
from config import DeployConfig
from constructs import Construct

from stacks.foundation_stack import FoundationStack
from stacks.messaging_stack import MessagingStack

SOURCE_ROOT = str(Path(__file__).resolve().parents[2] / "src")
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
        self.code = lambda_.Code.from_asset(SOURCE_ROOT)

        self.webhook = self._function("webhook", memory=512, timeout=cdk.Duration.seconds(30))
        self.worker = self._function(
            "worker",
            memory=1024,
            timeout=cdk.Duration.minutes(config.queue_visibility_minutes),
        )
        self.scheduler = self._function("scheduler", memory=512, timeout=cdk.Duration.minutes(1))
        self.functions = {
            "webhook": self.webhook,
            "worker": self.worker,
            "scheduler": self.scheduler,
        }

        self._wire_webhook()
        self._wire_worker()
        self._wire_scheduler()
        self.http_api = self._http_api()

    def _function(self, name: str, memory: int, timeout: cdk.Duration) -> lambda_.Function:
        resource_name = self.config.resource(name)
        log_group = logs.LogGroup(
            self,
            f"{name.capitalize()}Logs",
            log_group_name=f"/aws/lambda/{resource_name}",
            retention=RETENTION.get(self.config.log_retention_days, logs.RetentionDays.ONE_MONTH),
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )
        return lambda_.Function(
            self,
            f"{name.capitalize()}Function",
            function_name=resource_name,
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            handler=f"repaso.lambdas.{name}.handler",
            code=self.code,
            memory_size=memory,
            timeout=timeout,
            environment=self._environment(),
            log_group=log_group,
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
        for path in ("/judge", "/judge/{proxy+}", "/health"):
            http_api.add_routes(
                path=path,
                methods=[apigwv2.HttpMethod.GET],
                integration=integration,
            )
        cdk.CfnOutput(self, "HttpApiUrl", value=http_api.api_endpoint)
        return http_api
