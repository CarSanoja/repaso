import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "infra"))

from intrinsics import collapse  # noqa: E402
from namespace import in_namespace  # noqa: E402
from namespace_guard import RESOURCE_POLICY_TYPES, _as_list, _documents  # noqa: E402

PROJECT = "repaso"
ANY_RESOURCE = "*"
INVOKE = ("bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream")

DECLARED_REACH = {
    ("bedrock", "foundation-model", INVOKE),
    ("bedrock", "inference-profile", INVOKE),
    (
        "bedrock-agentcore",
        "workload-identity-directory",
        (
            "bedrock-agentcore:GetWorkloadAccessToken",
            "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
            "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
        ),
    ),
    ("ecr", "repository", ("ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer")),
    ("logs", "log-group", ("logs:DescribeLogGroups",)),
    ("logs", "log-group", ("logs:CreateLogGroup", "logs:DescribeLogStreams")),
    ("logs", "log-group", ("logs:CreateLogStream", "logs:PutLogEvents")),
    (ANY_RESOURCE, ANY_RESOURCE, ("cloudwatch:PutMetricData",)),
    (ANY_RESOURCE, ANY_RESOURCE, ("ecr:GetAuthorizationToken",)),
    (ANY_RESOURCE, ANY_RESOURCE, ("logs:DeleteRetentionPolicy", "logs:PutRetentionPolicy")),
    (ANY_RESOURCE, ANY_RESOURCE, ("scheduler:ListSchedules",)),
    (ANY_RESOURCE, ANY_RESOURCE, ("textract:DetectDocumentText",)),
    (
        ANY_RESOURCE,
        ANY_RESOURCE,
        (
            "xray:GetSamplingRules",
            "xray:GetSamplingTargets",
            "xray:PutTelemetryRecords",
            "xray:PutTraceSegments",
        ),
    ),
}


def kind(resource: str) -> tuple[str, str]:
    if not resource.startswith("arn:"):
        return ANY_RESOURCE, ANY_RESOURCE
    parts = resource.split(":")
    return parts[2], parts[5].split("/")[0]


def reach(assembly: Path) -> set[tuple[str, str, tuple[str, ...]]]:
    found = set()
    for path in sorted(assembly.glob("repaso-*.template.json")):
        template = json.loads(path.read_text(encoding="utf-8"))
        for resource in (template.get("Resources") or {}).values():
            self_scoped = resource.get("Type") in RESOURCE_POLICY_TYPES
            for document in _documents(resource.get("Properties") or {}):
                found |= _statements(document, self_scoped)
    return found


def _statements(document: dict, self_scoped: bool) -> set:
    found = set()
    for statement in _as_list(document.get("Statement")):
        if not isinstance(statement, dict):
            continue
        actions = tuple(
            sorted(
                collapse(entry, PROJECT)
                for entry in _as_list(statement.get("Action") or statement.get("NotAction"))
            )
        )
        for entry in _as_list(statement.get("Resource")):
            value = collapse(entry, PROJECT)
            if in_namespace(value, PROJECT) or (self_scoped and value == ANY_RESOURCE):
                continue
            found.add((*kind(value), actions))
    return found


@pytest.mark.parametrize("mode", ["assembly", "ephemeral_assembly"])
def test_nothing_reaches_outside_the_namespace_that_is_not_declared(request, mode):
    assert reach(request.getfixturevalue(mode)) == DECLARED_REACH


@pytest.mark.parametrize("mode", ["assembly", "ephemeral_assembly"])
def test_publishing_metrics_is_confined_to_a_metric_namespace(request, mode):
    assembly = request.getfixturevalue(mode)
    conditions = []
    for path in sorted(assembly.glob("repaso-*.template.json")):
        template = json.loads(path.read_text(encoding="utf-8"))
        for resource in (template.get("Resources") or {}).values():
            for document in _documents(resource.get("Properties") or {}):
                for statement in _as_list(document.get("Statement")):
                    if not isinstance(statement, dict):
                        continue
                    if "cloudwatch:PutMetricData" in _as_list(statement.get("Action")):
                        conditions.append(statement.get("Condition"))

    assert conditions
    for condition in conditions:
        assert "cloudwatch:namespace" in condition["StringEquals"]
