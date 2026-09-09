import re
from fnmatch import fnmatchcase

from intrinsics import OWN, collapse

SEGMENTS = re.compile(r"[:/]")
ACCOUNT_ROOT = "arn:aws:iam::<account>:root"

NAME_PROPERTIES = {
    "AWS::ApiGatewayV2::Api": ("Name",),
    "AWS::Bedrock::Guardrail": ("Name",),
    "AWS::BedrockAgentCore::Runtime": ("AgentRuntimeName",),
    "AWS::Budgets::Budget": ("Budget.BudgetName",),
    "AWS::CloudWatch::Alarm": ("AlarmName",),
    "AWS::CloudWatch::Dashboard": ("DashboardName",),
    "AWS::DynamoDB::Table": ("TableName",),
    "AWS::Events::EventBus": ("Name",),
    "AWS::Events::Rule": ("Name",),
    "AWS::IAM::Role": ("RoleName", "Policies[].PolicyName"),
    "AWS::KMS::Alias": ("AliasName",),
    "AWS::Lambda::Function": ("FunctionName",),
    "AWS::Logs::LogGroup": ("LogGroupName",),
    "AWS::S3::Bucket": ("BucketName",),
    "AWS::SNS::Topic": ("TopicName",),
    "AWS::SQS::Queue": ("QueueName",),
    "AWS::SSM::Parameter": ("Name",),
    "AWS::Scheduler::ScheduleGroup": ("Name",),
    "AWS::SecretsManager::Secret": ("Name",),
    "Custom::LogRetention": ("LogGroupName",),
}

SETTING_PROPERTIES = {
    "AWS::Lambda::Function": "Environment.Variables",
    "AWS::BedrockAgentCore::Runtime": "EnvironmentVariables",
}

SETTING_SUFFIXES = (
    "_ARN",
    "_BUCKET",
    "_BUS",
    "_GROUP",
    "_PARAMETER",
    "_QUEUE",
    "_SECRET_NAME",
    "_TABLE",
    "_TOPIC",
)

SERVICE_ARNS = ("arn:aws:iam::aws:policy/*", ACCOUNT_ROOT)

SHARED_ACCESS = (
    (
        "[*]",
        (
            "cloudwatch:PutMetricData",
            "ecr:GetAuthorizationToken",
            "logs:DeleteRetentionPolicy",
            "logs:PutRetentionPolicy",
            "scheduler:ListSchedules",
            "textract:DetectDocumentText",
            "xray:*",
        ),
    ),
    (
        "arn:aws:bedrock:*::foundation-model/*",
        ("bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"),
    ),
    (
        "arn:aws:bedrock:*:<account>:inference-profile/*",
        ("bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"),
    ),
    (
        "arn:aws:bedrock-agentcore:*:<account>:workload-identity-directory/default",
        ("bedrock-agentcore:GetWorkloadAccessToken*",),
    ),
    ("arn:aws:logs:*:<account>:log-group:[*]", ("logs:DescribeLogGroups",)),
    (
        "arn:aws:logs:*:<account>:log-group:/aws/bedrock-agentcore/runtimes/*",
        (
            "logs:CreateLogGroup",
            "logs:CreateLogStream",
            "logs:DescribeLogStreams",
            "logs:PutLogEvents",
        ),
    ),
)

BOOTSTRAP_ACCESS = (
    "arn:aws:ecr:*:<account>:repository/cdk-{qualifier}-container-assets-*",
    ("ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"),
)


def in_namespace(value: str, project: str) -> bool:
    for segment in SEGMENTS.split(value):
        bare = segment.rstrip("*")
        if OWN in bare or bare == project or bare.startswith(f"{project}-"):
            return True
    return False


def shared_access(qualifier: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    pattern, actions = BOOTSTRAP_ACCESS
    return (*SHARED_ACCESS, (pattern.format(qualifier=qualifier), actions))


def declared_access(resource: str, actions: tuple[str, ...], qualifier: str) -> bool:
    for pattern, allowed in shared_access(qualifier):
        if not fnmatchcase(resource, pattern):
            continue
        if all(any(fnmatchcase(action, ok) for ok in allowed) for action in actions):
            return True
    return False


def declared_arn(value: str) -> bool:
    return any(fnmatchcase(value, pattern) for pattern in SERVICE_ARNS)


def names(properties: dict, resource_type: str, owner: str) -> list[str]:
    found: list[str] = []
    for path in NAME_PROPERTIES.get(resource_type, ()):
        _descend(properties, path.split("."), owner, found)
    return found


def settings(properties: dict, resource_type: str, owner: str) -> list[tuple[str, str]]:
    path = SETTING_PROPERTIES.get(resource_type)
    if path is None:
        return []
    holder: list[object] = []
    _collect(properties, path.split("."), holder)
    pairs: list[tuple[str, str]] = []
    for block in holder:
        if not isinstance(block, dict):
            continue
        for key, value in block.items():
            if key.endswith(SETTING_SUFFIXES):
                pairs.append((key, collapse(value, owner)))
    return pairs


def _descend(node: object, parts: list[str], owner: str, out: list[str]) -> None:
    _walk(node, parts, lambda leaf: out.append(collapse(leaf, owner)))


def _collect(node: object, parts: list[str], out: list[object]) -> None:
    _walk(node, parts, out.append)


def _walk(node: object, parts: list[str], leaf) -> None:
    if not parts:
        leaf(node)
        return
    head, rest = parts[0], parts[1:]
    if head.endswith("[]"):
        child = node.get(head[:-2]) if isinstance(node, dict) else None
        for item in child or []:
            _walk(item, rest, leaf)
        return
    child = node.get(head) if isinstance(node, dict) else None
    if child is not None:
        _walk(child, rest, leaf)
