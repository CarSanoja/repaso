import json
from pathlib import Path

BUCKET = "AWS::S3::Bucket"
BUCKET_POLICY = "AWS::S3::BucketPolicy"
TABLE = "AWS::DynamoDB::Table"
TLS_FLOOR = 1.2


def resources(assembly: Path, stack: str) -> dict:
    raw = (assembly / f"repaso-{stack}.template.json").read_text(encoding="utf-8")
    return json.loads(raw)["Resources"]


def of_type(assembly: Path, stack: str, kind: str) -> list[dict]:
    return [r["Properties"] for r in resources(assembly, stack).values() if r["Type"] == kind]


def denials(policy: dict) -> list[dict]:
    return [s for s in policy["PolicyDocument"]["Statement"] if s["Effect"] == "Deny"]


def test_every_bucket_refuses_plaintext_transport(assembly):
    policies = of_type(assembly, "foundation", BUCKET_POLICY)
    assert len(policies) == len(of_type(assembly, "foundation", BUCKET))
    for policy in policies:
        conditions = json.dumps([s.get("Condition") for s in denials(policy)])
        assert '"aws:SecureTransport": "false"' in conditions


def test_every_bucket_refuses_an_obsolete_tls_version(assembly):
    for policy in of_type(assembly, "foundation", BUCKET_POLICY):
        floors = [
            s.get("Condition", {}).get("NumericLessThan", {}).get("s3:TlsVersion")
            for s in denials(policy)
        ]
        assert TLS_FLOOR in floors


def test_every_bucket_blocks_public_access(assembly):
    for bucket in of_type(assembly, "foundation", BUCKET):
        blocked = bucket["PublicAccessBlockConfiguration"]
        assert all(blocked[flag] for flag in blocked)


def test_the_material_bucket_is_encrypted_with_the_project_key(assembly):
    buckets = of_type(assembly, "foundation", BUCKET)
    managed = [
        b
        for b in buckets
        if "KMSMasterKeyID"
        in json.dumps(b["BucketEncryption"]["ServerSideEncryptionConfiguration"])
    ]
    assert len(managed) == 1
    assert "RepasoKey" in json.dumps(managed[0]["BucketEncryption"])


def test_the_table_holding_family_data_is_encrypted_with_the_project_key(assembly):
    tables = of_type(assembly, "foundation", TABLE)
    assert len(tables) == 1
    sse = tables[0]["SSESpecification"]
    assert sse["SSEEnabled"] is True
    assert sse["SSEType"] == "KMS"
    assert "RepasoKey" in json.dumps(sse["KMSMasterKeyId"])


def test_the_table_recovers_to_a_point_in_time(assembly):
    table = of_type(assembly, "foundation", TABLE)[0]
    recovery = table["PointInTimeRecoverySpecification"]
    assert recovery["PointInTimeRecoveryEnabled"] is True


def test_the_public_endpoint_is_throttled(assembly):
    stages = of_type(assembly, "api", "AWS::ApiGatewayV2::Stage")
    assert len(stages) == 1
    settings = stages[0]["DefaultRouteSettings"]
    assert settings["ThrottlingRateLimit"] > 0
    assert settings["ThrottlingBurstLimit"] >= settings["ThrottlingRateLimit"]


def test_material_expires_on_a_stated_schedule(assembly):
    buckets = of_type(assembly, "foundation", BUCKET)
    rules = [b["LifecycleConfiguration"]["Rules"] for b in buckets if "LifecycleConfiguration" in b]
    assert len(rules) == 1
    assert rules[0][0]["ExpirationInDays"] > 0
    assert rules[0][0]["Status"] == "Enabled"
