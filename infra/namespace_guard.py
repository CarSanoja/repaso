from pathlib import Path

from intrinsics import FOREIGN_IMPORT, collapse, is_call
from namespace import (
    ACCOUNT_ROOT,
    declared_access,
    declared_arn,
    in_namespace,
    names,
    settings,
)

POLICY_KEYS = ("PolicyDocument", "AssumeRolePolicyDocument", "KeyPolicy")
ARN_PREFIX = "arn:"
SELF = "*"
DENY = "Deny"

RESOURCE_POLICY_TYPES = frozenset(
    {
        "AWS::ECR::Repository",
        "AWS::Events::EventBusPolicy",
        "AWS::KMS::Key",
        "AWS::Logs::ResourcePolicy",
        "AWS::S3::BucketPolicy",
        "AWS::SNS::TopicPolicy",
        "AWS::SQS::QueuePolicy",
        "AWS::SecretsManager::ResourcePolicy",
    }
)


class NamespaceViolation(Exception):
    pass


def enforce(templates: dict[str, dict], project: str, qualifier: str) -> None:
    found = violations(templates, project, qualifier)
    if not found:
        return
    report = "\n".join(f"  {line}" for line in found)
    raise NamespaceViolation(
        f"{len(found)} resource reference(s) outside the {project} namespace:\n{report}"
    )


def enforce_assembly(assembly, project: str, qualifier: str) -> None:
    templates = {artifact.stack_name: artifact.template for artifact in assembly.stacks}
    try:
        enforce(templates, project, qualifier)
    except NamespaceViolation:
        for artifact in assembly.stacks:
            Path(assembly.directory, artifact.template_file).unlink(missing_ok=True)
        raise


def violations(templates: dict[str, dict], project: str, qualifier: str) -> list[str]:
    found: list[str] = []
    for stack in sorted(templates):
        template = templates[stack]
        for logical_id, resource in (template.get("Resources") or {}).items():
            for problem in _resource(resource, project, qualifier):
                found.append(f"{stack}.{logical_id}: {problem}")
        for name, output in (template.get("Outputs") or {}).items():
            export = collapse((output.get("Export") or {}).get("Name", ""), project)
            if export and not in_namespace(export, project):
                found.append(f"{stack}.{name}: exports {export}")
    return found


def _resource(resource: dict, project: str, qualifier: str) -> list[str]:
    properties = resource.get("Properties") or {}
    resource_type = resource.get("Type", "")
    problems = [
        f"names {value}"
        for value in names(properties, resource_type, project)
        if value and not in_namespace(value, project)
    ]
    problems += [
        f"{key} points at {value}"
        for key, value in settings(properties, resource_type, project)
        if value and not in_namespace(value, project)
    ]
    self_scoped = resource_type in RESOURCE_POLICY_TYPES
    for document in _documents(properties):
        for statement in _as_list(document.get("Statement")):
            problems += _statement(statement, project, qualifier, self_scoped)
    problems += _plain_arns(properties, project)
    return problems


def _statement(statement: dict, project: str, qualifier: str, self_scoped: bool) -> list[str]:
    if not isinstance(statement, dict):
        return []
    actions = tuple(
        collapse(entry, project)
        for entry in _as_list(statement.get("Action") or statement.get("NotAction"))
    )
    problems = []
    for entry in _as_list(statement.get("Resource")):
        value = collapse(entry, project)
        if self_scoped and value == SELF:
            continue
        if in_namespace(value, project) or declared_access(value, actions, qualifier):
            continue
        problems.append(f"{' '.join(actions) or 'a statement'} may reach {value}")
    if statement.get("Effect") == DENY:
        return problems
    for value in _principals(statement, project):
        if value == ACCOUNT_ROOT or in_namespace(value, project):
            continue
        problems.append(f"trusts principal {value}")
    return problems


def _principals(statement: dict, project: str) -> list[str]:
    principal = statement.get("Principal")
    if isinstance(principal, str):
        return [principal]
    if not isinstance(principal, dict):
        return []
    return [collapse(entry, project) for entry in _as_list(principal.get("AWS"))]


def _plain_arns(node: object, project: str) -> list[str]:
    problems: list[str] = []
    if isinstance(node, str) or is_call(node):
        value = collapse(node, project)
        if FOREIGN_IMPORT in value:
            problems.append(f"imports {value}")
        elif value.startswith(ARN_PREFIX) and not in_namespace(value, project):
            if not declared_arn(value):
                problems.append(f"refers to {value}")
        return problems
    if isinstance(node, dict):
        for key, child in node.items():
            if key not in POLICY_KEYS:
                problems += _plain_arns(child, project)
    elif isinstance(node, list):
        for item in node:
            problems += _plain_arns(item, project)
    return problems


def _documents(node: object):
    if isinstance(node, dict):
        for key, child in node.items():
            if key in POLICY_KEYS and isinstance(child, dict):
                yield child
            else:
                yield from _documents(child)
    elif isinstance(node, list):
        for item in node:
            yield from _documents(item)


def _as_list(value: object) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]
