import json
import re
from pathlib import Path
from typing import Any

import yaml
from aws_cdk import aws_iam as iam

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_DIR = REPO_ROOT / "deploy" / "agentcore"
IAM_DIR = DEPLOY_DIR / "iam"
RUNTIME_YAML = DEPLOY_DIR / "runtime.yaml"
DOCKERFILE = "deploy/agentcore/Dockerfile"

ENVIRONMENT_GROUPS = ("region", "resources", "runtime_only", "models", "tuning")
UNRESOLVED = re.compile(r"REPASO_[A-Z_]+")


def load_contract() -> dict[str, Any]:
    return yaml.safe_load(RUNTIME_YAML.read_text(encoding="utf-8"))


def environment(contract: dict[str, Any], overrides: dict[str, str]) -> dict[str, str]:
    block = contract["environment"]
    declared: dict[str, str] = {}
    for group in ENVIRONMENT_GROUPS:
        for name, value in (block.get(group) or {}).items():
            declared[name] = str(value)
    declared.update(overrides)
    never_set = set(block.get("never_set") or ())
    return {
        name: value
        for name, value in declared.items()
        if value and name not in never_set
    }


def _resolved(filename: str, values: dict[str, str]) -> dict[str, Any]:
    raw = (IAM_DIR / filename).read_text(encoding="utf-8")
    for placeholder, value in values.items():
        raw = raw.replace(placeholder, value)
    return json.loads(raw)


def trust_principal(filename: str, values: dict[str, str]) -> iam.ServicePrincipal:
    statement = _resolved(filename, values)["Statement"][0]
    return iam.ServicePrincipal(
        statement["Principal"]["Service"], conditions=statement.get("Condition")
    )


def policy_document(filename: str, values: dict[str, str]) -> iam.PolicyDocument:
    document = _resolved(filename, values)
    statements = [
        statement
        for statement in document["Statement"]
        if not UNRESOLVED.search(json.dumps(statement))
    ]
    return iam.PolicyDocument.from_json({**document, "Statement": statements})
