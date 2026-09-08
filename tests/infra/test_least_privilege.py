import json
from pathlib import Path

LAMBDA_ROLES = ("WebhookFunction", "WorkerFunction", "SchedulerFunction")
MODEL_ACTIONS = ("bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream")
WILDCARD_MODEL = "foundation-model/*"


def resources(assembly: Path, stack: str) -> dict:
    raw = (assembly / f"repaso-{stack}.template.json").read_text(encoding="utf-8")
    return json.loads(raw)["Resources"]


def inline_statements(assembly: Path, stack: str) -> list[tuple[str, dict]]:
    found = []
    for logical, resource in resources(assembly, stack).items():
        properties = resource["Properties"]
        documents = []
        if resource["Type"] == "AWS::IAM::Policy":
            documents.append(properties["PolicyDocument"])
        if resource["Type"] == "AWS::IAM::Role":
            documents.extend(p["PolicyDocument"] for p in properties.get("Policies", []))
        for document in documents:
            found.extend((logical, statement) for statement in document["Statement"])
    return found


def actions_of(statement: dict) -> list[str]:
    action = statement.get("Action")
    return [action] if isinstance(action, str) else list(action or [])


def lambda_statements(assembly: Path) -> list[tuple[str, dict]]:
    return [
        (logical, statement)
        for logical, statement in inline_statements(assembly, "api")
        if any(role in logical for role in LAMBDA_ROLES)
    ]


def test_no_lambda_role_may_invoke_a_model(assembly):
    for logical, statement in lambda_statements(assembly):
        granted = set(actions_of(statement))
        assert not granted & set(MODEL_ACTIONS), logical


def test_no_lambda_role_may_reach_the_material_bucket(assembly):
    for logical, statement in lambda_statements(assembly):
        services = {action.split(":")[0] for action in actions_of(statement)}
        assert "s3" not in services, logical


def test_a_lambda_key_grant_names_the_project_key(assembly):
    for logical, statement in lambda_statements(assembly):
        if not any(action.startswith("kms:") for action in actions_of(statement)):
            continue
        rendered = json.dumps(statement["Resource"])
        assert "RepasoKey" in rendered, logical
        assert statement["Resource"] != "*", logical


def test_only_the_webhook_may_read_a_secret(assembly):
    readers = {
        logical
        for logical, statement in lambda_statements(assembly)
        if any(action.startswith("secretsmanager:") for action in actions_of(statement))
    }
    assert all("WebhookFunction" in logical for logical in readers), readers


def test_no_lambda_statement_grants_an_unconstrained_resource(assembly):
    for logical, statement in lambda_statements(assembly):
        if statement.get("Resource") == "*":
            assert statement.get("Condition"), logical


def test_the_runtime_names_the_models_it_may_invoke(assembly):
    granted = [
        statement
        for _, statement in inline_statements(assembly, "agentcore")
        if set(actions_of(statement)) & set(MODEL_ACTIONS)
    ]
    assert granted, "the runtime must still be able to invoke a model"
    for statement in granted:
        rendered = json.dumps(statement["Resource"])
        assert WILDCARD_MODEL not in rendered, rendered
        assert "anthropic.claude" in rendered and "amazon.nova" in rendered


def function_actions(assembly: Path, prefix: str) -> set[str]:
    granted: set[str] = set()
    for logical, statement in inline_statements(assembly, "api"):
        if logical.startswith(prefix):
            granted.update(actions_of(statement))
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
    assert not [action for action in granted if action.startswith(("s3:", "bedrock"))]
