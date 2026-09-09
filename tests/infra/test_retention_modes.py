import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "infra"))

pytest.importorskip("aws_cdk")

from retention import DeploymentMode  # noqa: E402

DATA_RESOURCES = {
    "RepasoKeyA8A68261": "AWS::KMS::Key",
    "MediaBucketBCBB02BA": "AWS::S3::Bucket",
    "TableCD117FA1": "AWS::DynamoDB::Table",
}
AUTO_DELETE = "Custom::S3AutoDeleteObjects"
MEDIA_AUTO_DELETE = "MediaBucketAutoDeleteObjectsCustomResourceBC0A7C44"


def resources(templates: dict, stack: str) -> dict:
    return templates[stack]["Resources"]


def outputs(templates: dict, stack: str) -> dict:
    return {name: value["Value"] for name, value in templates[stack]["Outputs"].items()}


def test_the_default_mode_is_the_one_that_keeps_family_data():
    assert DeploymentMode.parse(None) is DeploymentMode.DURABLE
    assert DeploymentMode.parse("") is DeploymentMode.DURABLE
    assert DeploymentMode.DURABLE.keeps_data


@pytest.mark.parametrize("raw", ["persistent", "delete", "DURABLE ephemeral", "true"])
def test_a_mode_nobody_defined_stops_the_synthesis(raw):
    with pytest.raises(ValueError, match="deployment_mode"):
        DeploymentMode.parse(raw)


@pytest.mark.parametrize("raw", ["ephemeral", "EPHEMERAL", " Ephemeral "])
def test_the_pilot_mode_is_reachable_however_it_is_typed(raw):
    assert DeploymentMode.parse(raw) is DeploymentMode.EPHEMERAL


@pytest.mark.parametrize("logical_id", DATA_RESOURCES)
def test_durable_keeps_the_key_the_media_and_the_table(durable, logical_id):
    resource = resources(durable, "foundation")[logical_id]

    assert resource["Type"] == DATA_RESOURCES[logical_id]
    assert resource["DeletionPolicy"] == "Retain"
    assert resource["UpdateReplacePolicy"] == "Retain"


@pytest.mark.parametrize("logical_id", DATA_RESOURCES)
def test_ephemeral_lets_every_one_of_them_go(ephemeral, logical_id):
    resource = resources(ephemeral, "foundation")[logical_id]

    assert resource["DeletionPolicy"] == "Delete"
    assert resource["UpdateReplacePolicy"] == "Delete"


def test_ephemeral_empties_the_media_bucket_before_it_goes(ephemeral):
    foundation = resources(ephemeral, "foundation")

    assert foundation[MEDIA_AUTO_DELETE]["Type"] == AUTO_DELETE
    assert foundation["RepasoKeyA8A68261"]["Properties"]["PendingWindowInDays"] == 7


def test_durable_leaves_the_media_bucket_full(durable):
    foundation = resources(durable, "foundation")

    assert MEDIA_AUTO_DELETE not in foundation
    assert "PendingWindowInDays" not in foundation["RepasoKeyA8A68261"]["Properties"]


def test_every_stack_says_which_mode_produced_it(durable, ephemeral):
    assert all(outputs(durable, stack)["DeploymentMode"] == "durable" for stack in durable)
    assert all(outputs(ephemeral, stack)["DeploymentMode"] == "ephemeral" for stack in ephemeral)


def test_the_foundation_names_what_would_survive_a_delete(durable, ephemeral):
    assert outputs(durable, "foundation")["RetainedOnDelete"] == (
        "kms key, media bucket, state table"
    )
    assert outputs(ephemeral, "foundation")["RetainedOnDelete"] == "none"
