"""Whether anything the stacks intend to create is already standing in the account."""

from preflight_account import PROJECT
from preflight_findings import AwsSession, Finding, Status, absent, code_of, present

SECRETS = (f"{PROJECT}/telegram", f"{PROJECT}/judge", f"{PROJECT}/pilot-invite-codes")
STACKS = ("foundation", "messaging", "guardrails", "api", "agentcore", "observability")
NAMED = (
    ("dynamodb", "describe_table", {"TableName": PROJECT}),
    ("events", "describe_event_bus", {"Name": PROJECT}),
    ("scheduler", "get_schedule_group", {"Name": PROJECT}),
    ("kms", "describe_key", {"KeyId": f"alias/{PROJECT}"}),
    ("iam", "get_role", {"RoleName": f"{PROJECT}-agentcore-runtime"}),
    ("iam", "get_role", {"RoleName": f"{PROJECT}-scheduler"}),
    ("sqs", "get_queue_url", {"QueueName": f"{PROJECT}-ingest"}),
    ("sqs", "get_queue_url", {"QueueName": f"{PROJECT}-tutor"}),
    ("sqs", "get_queue_url", {"QueueName": f"{PROJECT}-quality"}),
    ("sqs", "get_queue_url", {"QueueName": f"{PROJECT}-scheduler-dlq"}),
)
TAKEN_REMEDY = "rename or remove it before deploying; the stacks claim this exact name"
DELETION_REMEDY = "aws secretsmanager restore-secret --secret-id {name}, or wait out the window"
UPDATE_DETAIL = "already exists, so this run is an update and not a first deployment"


def secrets(session: AwsSession) -> list[Finding]:
    client = session.client("secretsmanager")
    return [_secret(client, name) for name in SECRETS]


def _secret(client, name: str) -> Finding:
    try:
        described = client.describe_secret(SecretId=name)
    except Exception as error:
        if absent(error):
            detail = "absent, and the foundation stack creates it"
            return Finding(check=f"secret {name}", status=Status.OK, detail=detail)
        return Finding(check=f"secret {name}", status=Status.WARN, detail=code_of(error))
    if described.get("DeletedDate"):
        return Finding(
            check=f"secret {name}",
            status=Status.BLOCKER,
            detail="scheduled for deletion, and a new secret cannot take the name",
            remedy=DELETION_REMEDY.format(name=name),
        )
    return Finding(
        check=f"secret {name}", status=Status.WARN, detail="already exists", remedy=TAKEN_REMEDY
    )


def taken(session: AwsSession) -> list[Finding]:
    findings: list[Finding] = []
    for service, method, kwargs in NAMED:
        label = f"{service} {next(iter(kwargs.values()))}"
        standing = present(session, service, method, kwargs)
        if standing is None:
            findings.append(Finding(check=label, status=Status.WARN, detail="not readable"))
        elif standing:
            findings.append(
                Finding(
                    check=label,
                    status=Status.BLOCKER,
                    detail="name already taken",
                    remedy=TAKEN_REMEDY,
                )
            )
    return findings


def stacks(session: AwsSession) -> list[Finding]:
    findings: list[Finding] = []
    for name in STACKS:
        stack = f"{PROJECT}-{name}"
        if present(session, "cloudformation", "describe_stacks", {"StackName": stack}):
            findings.append(
                Finding(check=f"stack {stack}", status=Status.WARN, detail=UPDATE_DETAIL)
            )
    return findings
