import json
from hashlib import sha256

import aws_cdk as cdk
from aws_cdk import aws_bedrock as bedrock
from aws_cdk import aws_ssm as ssm
from config import DeployConfig
from constructs import Construct

HIGH = "HIGH"
NONE = "NONE"
ANONYMIZE = "ANONYMIZE"

HARM_FILTERS = ("HATE", "INSULTS", "SEXUAL", "VIOLENCE", "MISCONDUCT")
PROMPT_ATTACK = "PROMPT_ATTACK"
PII_ENTITIES = ("NAME", "PHONE", "EMAIL", "ADDRESS", "AGE")
PII_DIRECTIONS = ("input", "output")

BLOCKED_INPUT = (
    "No puedo ayudarte con eso. Si necesitas hablar de algo asi, "
    "busca a tu representante o a un adulto de confianza."
)
BLOCKED_OUTPUT = (
    "Prefiero no responder eso. Sigamos con tu repaso y me cuentas "
    "en que ejercicio te quedaste."
)

DESCRIPTION = (
    "Screens every message exchanged with a student before it reaches a model "
    "and every answer before it reaches the family"
)
VERSION_DESCRIPTION = "Published by the repaso guardrails stack for policy {digest}"


def policy_digest() -> str:
    shape = json.dumps(
        [
            HARM_FILTERS,
            PROMPT_ATTACK,
            PII_ENTITIES,
            PII_DIRECTIONS,
            HIGH,
            NONE,
            ANONYMIZE,
            BLOCKED_INPUT,
            BLOCKED_OUTPUT,
            DESCRIPTION,
        ],
        sort_keys=True,
    )
    return sha256(shape.encode("utf-8")).hexdigest()[:16]


class GuardrailsStack(cdk.Stack):
    def __init__(
        self, scope: Construct, construct_id: str, config: DeployConfig, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.config = config

        self.guardrail = bedrock.CfnGuardrail(
            self,
            "Guardrail",
            name=config.bare(),
            description=DESCRIPTION,
            blocked_input_messaging=BLOCKED_INPUT,
            blocked_outputs_messaging=BLOCKED_OUTPUT,
            content_policy_config=self._content_policy(),
            sensitive_information_policy_config=self._pii_policy(),
        )

        self.version = bedrock.CfnGuardrailVersion(
            self,
            "PublishedVersion",
            guardrail_identifier=self.guardrail.attr_guardrail_id,
            description=VERSION_DESCRIPTION.format(digest=policy_digest()),
        )

        self._publish("id", self.guardrail.attr_guardrail_id)
        self._publish("version", self.version.attr_version)

    @staticmethod
    def _content_policy() -> bedrock.CfnGuardrail.ContentPolicyConfigProperty:
        harm = [
            bedrock.CfnGuardrail.ContentFilterConfigProperty(
                type=filter_type, input_strength=HIGH, output_strength=HIGH
            )
            for filter_type in HARM_FILTERS
        ]
        attack = bedrock.CfnGuardrail.ContentFilterConfigProperty(
            type=PROMPT_ATTACK, input_strength=HIGH, output_strength=NONE
        )
        return bedrock.CfnGuardrail.ContentPolicyConfigProperty(
            filters_config=[*harm, attack]
        )

    @staticmethod
    def _pii_policy() -> bedrock.CfnGuardrail.SensitiveInformationPolicyConfigProperty:
        return bedrock.CfnGuardrail.SensitiveInformationPolicyConfigProperty(
            pii_entities_config=[
                bedrock.CfnGuardrail.PiiEntityConfigProperty(
                    type=entity,
                    action=ANONYMIZE,
                    input_action=ANONYMIZE,
                    input_enabled=True,
                    output_action=ANONYMIZE,
                    output_enabled=True,
                )
                for entity in PII_ENTITIES
            ]
        )

    def _publish(self, name: str, value: str) -> None:
        label = f"Guardrail{name.capitalize()}"
        ssm.StringParameter(
            self,
            f"{label}Parameter",
            parameter_name=self.config.parameter("guardrail", name),
            string_value=value,
        )
        cdk.CfnOutput(
            self,
            f"{label}Output",
            value=value,
            export_name=self.config.resource("guardrail", name),
        )
