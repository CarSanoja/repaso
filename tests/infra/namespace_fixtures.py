import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "infra"))

cdk = pytest.importorskip("aws_cdk")

from namespace_guard import (  # noqa: E402
    NamespaceViolation,
    enforce,
    enforce_assembly,
    violations,
)

__all__ = [
    "ALREADY_IN_THE_ACCOUNT",
    "NamespaceViolation",
    "PROJECT",
    "QUALIFIER",
    "bucket_policy_with",
    "enforce",
    "enforce_assembly",
    "found",
    "rendered",
    "role_with",
    "synthesized",
]

PROJECT = "repaso"
QUALIFIER = "repaso01"
MASKED_ACCOUNT = "000000000000"

ALREADY_IN_THE_ACCOUNT = (
    ("AWS::Lambda::Function", {"FunctionName": "quanta-prod-slack-notifier"}),
    ("AWS::Lambda::Function", {"FunctionName": "quanta-prod-rotate-voice-spool-key"}),
    ("AWS::S3::Bucket", {"BucketName": "quanta-prod-files"}),
    ("AWS::S3::Bucket", {"BucketName": "quanta-prod-db-backups"}),
    ("AWS::S3::Bucket", {"BucketName": "quanta-prod-log-archive"}),
    ("AWS::S3::Bucket", {"BucketName": "quanta-prod-config-delivery"}),
    ("AWS::S3::Bucket", {"BucketName": f"quanta-tfstate-{MASKED_ACCOUNT}"}),
    ("AWS::S3::Bucket", {"BucketName": f"trainium-frontier-{MASKED_ACCOUNT}"}),
    ("AWS::DynamoDB::Table", {"TableName": "quanta-terraform-locks"}),
)


def synthesized(tmp_path: Path, resources: list[tuple[str, dict]]):
    app = cdk.App(outdir=str(tmp_path))
    stack = cdk.Stack(app, "repaso-fixture")
    for index, (resource_type, properties) in enumerate(resources):
        cdk.CfnResource(stack, f"Fixture{index}", type=resource_type, properties=properties)
    return app.synth()


def rendered(tmp_path: Path, resources: list[tuple[str, dict]]) -> dict[str, dict]:
    assembly = synthesized(tmp_path, resources)
    return {artifact.stack_name: artifact.template for artifact in assembly.stacks}


def role_with(tmp_path: Path, statement: dict) -> dict[str, dict]:
    document = {"Version": "2012-10-17", "Statement": [statement]}
    return rendered(
        tmp_path,
        [
            (
                "AWS::IAM::Role",
                {
                    "RoleName": "repaso-fixture",
                    "AssumeRolePolicyDocument": {"Version": "2012-10-17", "Statement": []},
                    "Policies": [{"PolicyName": "repaso-fixture", "PolicyDocument": document}],
                },
            )
        ],
    )


def bucket_policy_with(tmp_path: Path, statement: dict) -> dict[str, dict]:
    return rendered(
        tmp_path,
        [
            (
                "AWS::S3::BucketPolicy",
                {
                    "Bucket": "repaso-material",
                    "PolicyDocument": {"Version": "2012-10-17", "Statement": [statement]},
                },
            )
        ],
    )


def found(templates: dict[str, dict]) -> list[str]:
    return violations(templates, PROJECT, QUALIFIER)
