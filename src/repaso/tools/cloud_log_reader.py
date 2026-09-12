from datetime import datetime

RUNTIME_GROUP_PREFIX = "/aws/bedrock-agentcore/runtimes"
RUNTIME_GROUP_SUFFIX = "DEFAULT"
EVENTS_KEY = "events"
MESSAGE_KEY = "message"
TOKEN_KEY = "nextToken"


def runtime_log_group(runtime_arn: str) -> str:
    identifier = runtime_arn.rsplit("/", 1)[-1]
    if not identifier:
        raise ValueError(f"no runtime id in {runtime_arn!r}")
    return f"{RUNTIME_GROUP_PREFIX}/{identifier}-{RUNTIME_GROUP_SUFFIX}"


def resolve_runtime_arn(region: str, parameter: str) -> str:
    import boto3

    client = boto3.Session(region_name=region).client("ssm")
    return client.get_parameter(Name=parameter)["Parameter"]["Value"]


def _milliseconds(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)


def read_messages(region: str, group: str, start: datetime, end: datetime) -> list[str]:
    import boto3

    client = boto3.Session(region_name=region).client("logs")
    request = {
        "logGroupName": group,
        "startTime": _milliseconds(start),
        "endTime": _milliseconds(end),
    }
    messages: list[str] = []
    token: str | None = None
    while True:
        page = client.filter_log_events(**request | ({TOKEN_KEY: token} if token else {}))
        messages.extend(event[MESSAGE_KEY] for event in page.get(EVENTS_KEY, []))
        token = page.get(TOKEN_KEY)
        if not token:
            return messages
