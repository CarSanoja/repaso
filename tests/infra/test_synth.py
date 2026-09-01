import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

assertions = pytest.importorskip("aws_cdk.assertions")

APP = Path(__file__).resolve().parents[2] / "infra" / "app.py"
ALERT_EMAIL = "alerts@example.com"
BUDGET_LIMITS = (25, 40)
STACKS = ("foundation", "messaging", "guardrails", "api", "agentcore", "observability")
HARM_FILTERS = ("HATE", "INSULTS", "SEXUAL", "VIOLENCE", "MISCONDUCT")
PII_ENTITIES = ("NAME", "PHONE", "EMAIL", "ADDRESS", "AGE")
NEVER_SET = ("REPASO_LOCAL_MODE", "REPASO_LOCAL_DATA_DIR", "REPASO_LIVE_TESTS")
QUEUES = ("ingest", "tutor", "quality")
GUARDRAIL = "AWS::Bedrock::Guardrail"
RUNTIME = "AWS::BedrockAgentCore::Runtime"
PARAMETER = "AWS::SSM::Parameter"


@pytest.fixture(scope="module")
def assembly(tmp_path_factory) -> Path:
    outdir = tmp_path_factory.mktemp("cloud-assembly")
    result = subprocess.run(
        [sys.executable, str(APP)],
        env={
            **os.environ,
            "CDK_OUTDIR": str(outdir),
            "CDK_CONTEXT_JSON": json.dumps({"alert_email": ALERT_EMAIL}),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return outdir


def template(assembly: Path, name: str):
    rendered = (assembly / f"repaso-{name}.template.json").read_text(encoding="utf-8")
    return assertions.Template.from_string(rendered)


def only(assembly: Path, stack: str, resource_type: str) -> dict:
    resources = template(assembly, stack).find_resources(resource_type)
    assert len(resources) == 1
    return next(iter(resources.values()))["Properties"]


@pytest.mark.parametrize("name", STACKS)
def test_every_stack_renders_a_template_with_resources(assembly, name):
    assert template(assembly, name).to_json()["Resources"]


def test_the_guardrail_filters_harm_hard_in_both_directions(assembly):
    filters = only(assembly, "guardrails", GUARDRAIL)["ContentPolicyConfig"][
        "FiltersConfig"
    ]
    strengths = {
        entry["Type"]: (entry["InputStrength"], entry["OutputStrength"]) for entry in filters
    }

    assert all(strengths[name] == ("HIGH", "HIGH") for name in HARM_FILTERS)
    assert strengths["PROMPT_ATTACK"] == ("HIGH", "NONE")


def test_the_guardrail_anonymizes_what_identifies_a_child(assembly):
    entities = only(assembly, "guardrails", GUARDRAIL)[
        "SensitiveInformationPolicyConfig"
    ]["PiiEntitiesConfig"]

    assert {entry["Type"]: entry["Action"] for entry in entities} == {
        name: "ANONYMIZE" for name in PII_ENTITIES
    }


def test_the_guardrail_refuses_in_spanish(assembly):
    guardrail = only(assembly, "guardrails", GUARDRAIL)

    assert "No puedo ayudarte" in guardrail["BlockedInputMessaging"]
    assert "Prefiero no responder" in guardrail["BlockedOutputsMessaging"]


def test_the_guardrail_is_published_and_reachable_from_ssm(assembly):
    stack = template(assembly, "guardrails")
    parameters = stack.find_resources(PARAMETER)

    stack.resource_count_is("AWS::Bedrock::GuardrailVersion", 1)
    assert sorted(entry["Properties"]["Name"] for entry in parameters.values()) == [
        "/repaso/guardrail/id",
        "/repaso/guardrail/version",
    ]


def test_the_runtime_is_a_public_http_container(assembly):
    runtime = only(assembly, "agentcore", RUNTIME)

    assert runtime["AgentRuntimeName"] == "repaso"
    assert runtime["NetworkConfiguration"]["NetworkMode"] == "PUBLIC"
    assert runtime["ProtocolConfiguration"] == "HTTP"
    assert runtime["AgentRuntimeArtifact"]["ContainerConfiguration"]["ContainerUri"]


def test_the_runtime_environment_holds_no_empty_or_forbidden_value(assembly):
    environment = only(assembly, "agentcore", RUNTIME)["EnvironmentVariables"]

    assert all(value for value in environment.values())
    assert not [name for name in NEVER_SET if name in environment]
    assert "REPASO_TELEGRAM_TOKEN" not in environment
    assert environment["REPASO_MODEL_GENERATE"]


def test_the_execution_role_drops_the_statement_with_no_resource(assembly):
    role = only(assembly, "agentcore", "AWS::IAM::Role")
    statements = [
        statement
        for policy in role["Policies"]
        for statement in policy["PolicyDocument"]["Statement"]
    ]
    sids = [statement["Sid"] for statement in statements]

    assert "REPASO_" not in json.dumps(statements)
    assert "IntakeGuardrail" in sids
    assert "CurriculumKnowledgeBaseRetrieve" not in sids


def test_the_runtime_arn_is_published_for_whatever_invokes_it(assembly):
    assert only(assembly, "agentcore", PARAMETER)["Name"] == "/repaso/agentcore/runtime-arn"


def test_the_budgets_warn_the_configured_address(assembly):
    budgets = template(assembly, "foundation").find_resources("AWS::Budgets::Budget")
    alerted = {
        entry["Properties"]["Budget"]["BudgetLimit"]["Amount"]: entry["Properties"][
            "NotificationsWithSubscribers"
        ][0]["Subscribers"][0]["Address"]
        for entry in budgets.values()
    }

    assert alerted == {limit: ALERT_EMAIL for limit in BUDGET_LIMITS}


def test_every_work_queue_has_a_dead_letter_queue_behind_it(assembly):
    queues = {
        entry["Properties"]["QueueName"]: entry["Properties"]
        for entry in template(assembly, "messaging").find_resources("AWS::SQS::Queue").values()
    }

    for name in QUEUES:
        assert f"repaso-{name}-dlq" in queues
        assert queues[f"repaso-{name}"]["RedrivePolicy"]["maxReceiveCount"] == 3
