import aws_cdk as cdk
from aws_cdk import aws_bedrockagentcore as agentcore
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_ssm as ssm
from config import DeployConfig
from constructs import Construct

from stacks.agentcore_contract import (
    DOCKERFILE,
    REPO_ROOT,
    environment,
    load_contract,
    policy_document,
    trust_principal,
)
from stacks.foundation_stack import FoundationStack
from stacks.guardrails_stack import GuardrailsStack
from stacks.messaging_stack import MessagingStack

BUILD_EXCLUDES = [
    ".git",
    ".github",
    ".ruff_cache",
    ".venv",
    "docs",
    "infra",
    "node_modules",
    "private",
    "scripts",
    "tests",
    "**/__pycache__",
]

POLICIES = {
    "runtime": "runtime-execution-policy.json",
    "data": "repaso-data-policy.json",
}
TRUST_POLICY = "trust-policy.json"
RUNTIME_ARN_PARAMETER = ("agentcore", "runtime-arn")


class AgentCoreStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        config: DeployConfig,
        foundation: FoundationStack,
        messaging: MessagingStack,
        guardrails: GuardrailsStack,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.config = config
        self.contract = load_contract()

        self.image = ecr_assets.DockerImageAsset(
            self,
            "RuntimeImage",
            directory=str(REPO_ROOT),
            file=DOCKERFILE,
            platform=ecr_assets.Platform.LINUX_ARM64,
            exclude=BUILD_EXCLUDES,
        )

        substitutions = self._substitutions(foundation, guardrails)
        self.role = iam.Role(
            self,
            "ExecutionRole",
            role_name=config.resource("agentcore", "runtime"),
            assumed_by=trust_principal(TRUST_POLICY, substitutions),
            inline_policies={
                config.resource("agentcore", name): policy_document(filename, substitutions)
                for name, filename in POLICIES.items()
            },
        )

        container = self.contract["container"]
        self.runtime = agentcore.CfnRuntime(
            self,
            "Runtime",
            agent_runtime_name=config.bare(),
            role_arn=self.role.role_arn,
            agent_runtime_artifact=agentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                container_configuration=agentcore.CfnRuntime.ContainerConfigurationProperty(
                    container_uri=self.image.image_uri
                )
            ),
            network_configuration=agentcore.CfnRuntime.NetworkConfigurationProperty(
                network_mode=container["network_mode"]
            ),
            protocol_configuration=self.contract["entrypoint"]["protocol"],
            lifecycle_configuration=agentcore.CfnRuntime.LifecycleConfigurationProperty(
                idle_runtime_session_timeout=container["idle_timeout_seconds"],
                max_lifetime=container["max_lifetime_seconds"],
            ),
            environment_variables=environment(
                self.contract, self._overrides(foundation, messaging, guardrails)
            ),
        )

        self._publish_runtime_arn()

    def _substitutions(
        self, foundation: FoundationStack, guardrails: GuardrailsStack
    ) -> dict[str, str]:
        return {
            "123456789012": self.account,
            "us-east-1": self.region,
            "REPASO_IMAGE_REPOSITORY_ARN": self.image.repository.repository_arn,
            "REPASO_MEDIA_BUCKET": foundation.media_bucket.bucket_name,
            "REPASO_CURRICULUM_BUCKET": foundation.curriculum_bucket.bucket_name,
            "REPASO_KEY_ID": foundation.key.key_id,
            "REPASO_GUARDRAIL_ID": guardrails.guardrail.attr_guardrail_id,
        }

    def _overrides(
        self,
        foundation: FoundationStack,
        messaging: MessagingStack,
        guardrails: GuardrailsStack,
    ) -> dict[str, str]:
        config = self.config
        return {
            "REPASO_AWS_REGION": self.region,
            "AWS_REGION": self.region,
            "AWS_DEFAULT_REGION": self.region,
            "REPASO_DDB_TABLE": foundation.table.table_name,
            "REPASO_MEDIA_BUCKET": foundation.media_bucket.bucket_name,
            "REPASO_CURRICULUM_BUCKET": foundation.curriculum_bucket.bucket_name,
            "REPASO_EVENT_BUS": messaging.bus.event_bus_name,
            "REPASO_SCHEDULER_GROUP": config.bare(),
            "REPASO_TELEGRAM_SECRET_NAME": config.secret("telegram"),
            "REPASO_JUDGE_CODE_SECRET_NAME": config.secret("judge"),
            "REPASO_GUARDRAIL_ID": guardrails.guardrail.attr_guardrail_id,
            "REPASO_GUARDRAIL_VERSION": guardrails.version.attr_version,
        }

    def _publish_runtime_arn(self) -> None:
        arn = self.runtime.attr_agent_runtime_arn
        ssm.StringParameter(
            self,
            "RuntimeArnParameter",
            parameter_name=self.config.parameter(*RUNTIME_ARN_PARAMETER),
            string_value=arn,
        )
        cdk.CfnOutput(
            self,
            "RuntimeArnOutput",
            value=arn,
            export_name=self.config.resource(*RUNTIME_ARN_PARAMETER),
        )
