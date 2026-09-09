from pathlib import Path

import aws_cdk as cdk
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_sqs as sqs
from config import DeployConfig
from constructs import Construct

from stacks.foundation_stack import FoundationStack
from stacks.messaging_stack import MessagingStack

REPO_ROOT = str(Path(__file__).resolve().parents[2])
DOCKERFILE = "deploy/lambda/Dockerfile"

BUILD_CONTEXT = [
    "*",
    "!pyproject.toml",
    "!requirements.lock",
    "!README.md",
    "!LICENSE",
    "!src",
    f"!{DOCKERFILE}",
    "**/__pycache__",
    "**/*.pyc",
    "**/*.egg-info",
]

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


def environment(
    config: DeployConfig, region: str, foundation: FoundationStack, messaging: MessagingStack
) -> dict[str, str]:
    return {
        "REPASO_AWS_REGION": region,
        "REPASO_DDB_TABLE": foundation.table.table_name,
        "REPASO_MEDIA_BUCKET": foundation.media_bucket.bucket_name,
        "REPASO_CURRICULUM_BUCKET": foundation.curriculum_bucket.bucket_name,
        "REPASO_EVENT_BUS": messaging.bus.event_bus_name,
        "REPASO_SCHEDULER_GROUP": config.bare(),
        "REPASO_LOCAL_DATA_DIR": "/tmp/repaso",
        "REPASO_CURRICULUM_SOURCE": "bundled",
        "REPASO_AGENTCORE_RUNTIME_ARN_PARAMETER": config.parameter("agentcore", "runtime-arn"),
        "REPASO_TELEGRAM_SECRET_NAME": config.secret("telegram"),
        "REPASO_JUDGE_CODE_SECRET_NAME": config.secret("judge"),
        "REPASO_INVITE_CODES_SECRET_NAME": config.secret("pilot-invite-codes"),
    }


def build_function(
    scope: Construct,
    config: DeployConfig,
    name: str,
    memory: int,
    timeout: cdk.Duration,
    reserved: int,
    variables: dict[str, str],
    dead_letter_queue: sqs.Queue | None = None,
) -> lambda_.Function:
    resource_name = config.resource(name)
    log_group = logs.LogGroup(
        scope,
        f"{name.capitalize()}Logs",
        log_group_name=f"/aws/lambda/{resource_name}",
        retention=RETENTION.get(config.log_retention_days, logs.RetentionDays.ONE_MONTH),
        removal_policy=cdk.RemovalPolicy.DESTROY,
    )
    return lambda_.DockerImageFunction(
        scope,
        f"{name.capitalize()}Function",
        function_name=resource_name,
        architecture=lambda_.Architecture.ARM_64,
        code=lambda_.DockerImageCode.from_image_asset(
            REPO_ROOT,
            file=DOCKERFILE,
            cmd=[f"repaso.lambdas.{name}.handler"],
            exclude=list(BUILD_CONTEXT),
            ignore_mode=cdk.IgnoreMode.DOCKER,
        ),
        memory_size=memory,
        timeout=timeout,
        reserved_concurrent_executions=reserved,
        environment=variables,
        log_group=log_group,
        dead_letter_queue=dead_letter_queue,
        dead_letter_queue_enabled=dead_letter_queue is not None,
    )
