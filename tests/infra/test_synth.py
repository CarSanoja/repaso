import json
import os
import re
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
NEVER_SET = ("REPASO_LOCAL_MODE", "REPASO_LIVE_TESTS")
QUEUES = ("ingest", "tutor", "quality")
GUARDRAIL = "AWS::Bedrock::Guardrail"
RUNTIME = "AWS::BedrockAgentCore::Runtime"
PARAMETER = "AWS::SSM::Parameter"
AGENTCORE_ASSETS = "repaso-agentcore.assets.json"
IMAGE_CONTEXT = {
    ".dockerignore",
    "LICENSE",
    "README.md",
    "deploy",
    "pyproject.toml",
    "requirements.lock",
    "src",
}
INVITE_CODES_SECRET = "repaso/pilot-invite-codes"


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
    filters = only(assembly, "guardrails", GUARDRAIL)["ContentPolicyConfig"]["FiltersConfig"]
    strengths = {
        entry["Type"]: (entry["InputStrength"], entry["OutputStrength"]) for entry in filters
    }

    assert all(strengths[name] == ("HIGH", "HIGH") for name in HARM_FILTERS)
    assert strengths["PROMPT_ATTACK"] == ("HIGH", "NONE")


def test_the_guardrail_anonymizes_what_identifies_a_child(assembly):
    entities = only(assembly, "guardrails", GUARDRAIL)["SensitiveInformationPolicyConfig"][
        "PiiEntitiesConfig"
    ]

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


def test_the_published_version_carries_the_digest_of_what_it_publishes(assembly):
    version = only(assembly, "guardrails", "AWS::Bedrock::GuardrailVersion")
    digest = version["Description"].split()[-1]

    assert re.fullmatch(r"[0-9a-f]{16}", digest)


def test_the_runtime_is_a_public_http_container(assembly):
    runtime = only(assembly, "agentcore", RUNTIME)

    assert runtime["AgentRuntimeName"] == "repaso"
    assert runtime["NetworkConfiguration"]["NetworkMode"] == "PUBLIC"
    assert runtime["ProtocolConfiguration"] == "HTTP"
    assert runtime["AgentRuntimeArtifact"]["ContainerConfiguration"]["ContainerUri"]


def runtime_image(assembly: Path) -> dict:
    manifest = json.loads((assembly / AGENTCORE_ASSETS).read_text(encoding="utf-8"))
    images = [
        i
        for i in manifest["dockerImages"].values()
        if i["source"]["dockerFile"] == "deploy/agentcore/Dockerfile"
    ]
    assert len(images) == 1
    return images[0]["source"]


def test_the_image_is_built_from_what_the_dockerfile_copies_and_nothing_else(assembly):
    source = runtime_image(assembly)
    context = assembly / source["directory"]

    assert {entry.name for entry in context.iterdir()} == IMAGE_CONTEXT
    assert (context / source["dockerFile"]).is_file()
    assert list(context.rglob("__pycache__")) == []


def test_the_runtime_environment_holds_no_empty_or_forbidden_value(assembly):
    environment = only(assembly, "agentcore", RUNTIME)["EnvironmentVariables"]

    assert all(value for value in environment.values())
    assert not [name for name in NEVER_SET if name in environment]
    assert "REPASO_TELEGRAM_TOKEN" not in environment
    assert environment["REPASO_MODEL_GENERATE"]
    assert environment["REPASO_LOCAL_DATA_DIR"] == "/tmp/repaso"


def role_statements(assembly: Path) -> list[dict]:
    roles = template(assembly, "agentcore").find_resources("AWS::IAM::Role")
    role = next(
        r["Properties"]
        for r in roles.values()
        if r["Properties"].get("RoleName") == "repaso-agentcore-runtime"
    )
    return [
        statement
        for policy in role["Policies"]
        for statement in policy["PolicyDocument"]["Statement"]
    ]


def test_the_execution_role_drops_the_statement_with_no_resource(assembly):
    statements = role_statements(assembly)
    sids = [statement["Sid"] for statement in statements]

    assert "REPASO_" not in json.dumps(statements)
    assert "IntakeGuardrail" in sids
    assert "CurriculumKnowledgeBaseRetrieve" not in sids


def test_listing_family_alarms_is_not_scoped_to_a_schedule_arn(assembly):
    statements = role_statements(assembly)
    listing = next(s for s in statements if s["Sid"] == "FamilyAlarmListing")
    lifecycle = next(s for s in statements if s["Sid"] == "FamilyAlarmSchedules")

    assert listing["Action"] == "scheduler:ListSchedules"
    assert listing["Resource"] == "*"
    assert "scheduler:ListSchedules" not in lifecycle["Action"]


def test_the_runtime_may_read_every_secret_it_resolves_at_run_time(assembly):
    granted = json.dumps(role_statements(assembly))
    environment = only(assembly, "agentcore", RUNTIME)["EnvironmentVariables"]

    assert environment["REPASO_INVITE_CODES_SECRET_NAME"] == INVITE_CODES_SECRET
    assert f"secret:{INVITE_CODES_SECRET}-*" in granted


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


def function_actions(assembly: Path, prefix: str) -> set[str]:
    policies = template(assembly, "api").find_resources("AWS::IAM::Policy")
    document = next(
        entry["Properties"]["PolicyDocument"]
        for name, entry in policies.items()
        if name.startswith(prefix)
    )
    granted: set[str] = set()
    for statement in document["Statement"]:
        action = statement["Action"]
        granted.update([action] if isinstance(action, str) else action)
    return granted


def test_the_worker_may_reach_the_runtime_and_nothing_the_runtime_reaches(assembly):
    granted = function_actions(assembly, "WorkerFunctionServiceRoleDefaultPolicy")

    assert "bedrock-agentcore:InvokeAgentRuntime" in granted
    assert "ssm:GetParameter" in granted
    assert "sqs:ReceiveMessage" in granted
    assert not [action for action in granted if action.startswith(("bedrock:", "dynamodb:"))]
    assert not [action for action in granted if action.startswith(("s3:", "kms:", "secrets"))]
    assert "events:PutEvents" not in granted


def test_the_webhook_writes_state_and_events_and_touches_no_media(assembly):
    granted = function_actions(assembly, "WebhookFunctionServiceRoleDefaultPolicy")

    assert {"dynamodb:PutItem", "secretsmanager:GetSecretValue", "events:PutEvents"} <= granted
    assert not [action for action in granted if action.startswith(("s3:", "kms:", "bedrock"))]


def test_a_schedule_tick_that_keeps_failing_lands_somewhere_visible(assembly):
    functions = {
        entry["Properties"]["FunctionName"]: entry["Properties"]
        for entry in template(assembly, "api").find_resources("AWS::Lambda::Function").values()
    }
    alarms = {
        entry["Properties"]["AlarmName"]
        for entry in template(assembly, "observability")
        .find_resources("AWS::CloudWatch::Alarm")
        .values()
    }

    assert functions["repaso-scheduler"]["DeadLetterConfig"]["TargetArn"]
    assert "repaso-scheduler-dlq" in {
        entry["Properties"]["QueueName"]
        for entry in template(assembly, "messaging").find_resources("AWS::SQS::Queue").values()
    }
    assert "repaso-scheduler-dlq-depth" in alarms
