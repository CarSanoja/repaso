from pathlib import Path

import pytest

from tests.infra.namespace_fixtures import (
    ALREADY_IN_THE_ACCOUNT,
    PROJECT,
    QUALIFIER,
    NamespaceViolation,
    enforce,
    enforce_assembly,
    found,
    rendered,
    synthesized,
)


def test_the_deployment_as_designed_stays_inside_its_own_namespace(durable, ephemeral):
    assert found(durable) == []
    assert found(ephemeral) == []


def test_the_report_names_every_stack_and_resource_that_failed(tmp_path):
    templates = rendered(tmp_path, list(ALREADY_IN_THE_ACCOUNT))

    with pytest.raises(NamespaceViolation) as failure:
        enforce(templates, PROJECT, QUALIFIER)

    message = str(failure.value)
    assert message.count("repaso-fixture.Fixture") == len(ALREADY_IN_THE_ACCOUNT)
    assert "quanta-terraform-locks" in message


def test_a_rejected_assembly_is_not_left_behind_to_be_deployed(tmp_path):
    assembly = synthesized(tmp_path, [("AWS::S3::Bucket", {"BucketName": "quanta-prod-files"})])
    written = [Path(assembly.directory, artifact.template_file) for artifact in assembly.stacks]

    assert all(path.is_file() for path in written)
    with pytest.raises(NamespaceViolation):
        enforce_assembly(assembly, PROJECT, QUALIFIER)

    assert [path for path in written if path.exists()] == []


def test_an_accepted_assembly_keeps_its_templates(tmp_path):
    assembly = synthesized(tmp_path, [("AWS::S3::Bucket", {"BucketName": "repaso-extra"})])
    enforce_assembly(assembly, PROJECT, QUALIFIER)

    assert all(
        Path(assembly.directory, artifact.template_file).is_file()
        for artifact in assembly.stacks
    )
