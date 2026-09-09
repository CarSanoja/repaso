import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "infra"))

pytest.importorskip("aws_cdk")

from tagging import TAG_PROPERTY, carries_no_tags  # noqa: E402

REQUIRED = {"project", "managed-by", "deployment-mode"}
IMPLICIT = (
    "CustomS3AutoDeleteObjectsCustomResourceProviderRole3B1BD092",
    "CustomS3AutoDeleteObjectsCustomResourceProviderHandler9D90184F",
)
BUDGET = "Budget25"


def tag_keys(resource: dict) -> set[str]:
    prop = TAG_PROPERTY.get(resource["Type"], "Tags")
    tags = (resource.get("Properties") or {}).get(prop)
    if isinstance(tags, list):
        return {entry["Key"] for entry in tags}
    if isinstance(tags, dict):
        return set(tags)
    return set()


def untagged(templates: dict[str, dict]) -> list[str]:
    missing = []
    for stack, template in templates.items():
        for logical_id, resource in template["Resources"].items():
            if carries_no_tags(resource["Type"]):
                continue
            if not REQUIRED <= tag_keys(resource):
                missing.append(f"{stack}.{logical_id} ({resource['Type']})")
    return missing


def validation_issues(assembly: Path) -> list:
    report = json.loads((assembly / "validation-report.json").read_text(encoding="utf-8"))
    return report["pluginReports"]


@pytest.mark.parametrize("mode", ["assembly", "ephemeral_assembly"])
def test_no_tag_lands_on_a_resource_cloudformation_refuses_to_tag(request, mode):
    assert validation_issues(request.getfixturevalue(mode)) == []


def test_nothing_the_durable_deployment_creates_is_untagged(durable):
    assert untagged(durable) == []


def test_nothing_the_ephemeral_deployment_creates_is_untagged(ephemeral):
    assert untagged(ephemeral) == []


@pytest.mark.parametrize("logical_id", IMPLICIT)
def test_what_cdk_adds_behind_the_stack_is_tagged_too(ephemeral, logical_id):
    assert REQUIRED <= tag_keys(ephemeral["foundation"]["Resources"][logical_id])


def test_the_budget_is_tagged_through_the_property_it_actually_has(durable):
    budget = durable["foundation"]["Resources"][BUDGET]

    assert "Tags" not in budget["Properties"]
    assert REQUIRED <= tag_keys(budget)


def test_the_mode_tag_follows_the_mode(durable, ephemeral):
    durable_key = durable["foundation"]["Resources"]["RepasoKeyA8A68261"]
    ephemeral_key = ephemeral["foundation"]["Resources"]["RepasoKeyA8A68261"]

    assert _value(durable_key, "deployment-mode") == "durable"
    assert _value(ephemeral_key, "deployment-mode") == "ephemeral"


def _value(resource: dict, key: str) -> str:
    tags = resource["Properties"]["Tags"]
    return next(entry["Value"] for entry in tags if entry["Key"] == key)
