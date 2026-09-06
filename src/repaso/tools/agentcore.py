import json
from hashlib import sha256


def invoke_runtime(event, settings):
    import boto3
    from botocore.config import Config

    session = boto3.Session(region_name=settings.aws_region)
    arn = settings.agentcore_runtime_arn
    if not arn:
        arn = session.client("ssm").get_parameter(Name=settings.agentcore_runtime_arn_parameter)[
            "Parameter"
        ]["Value"]
    # Stable tenancy and retry identity; no names or message content in the session ID.
    scope = event.family_id or str(event.payload.get("chat_ref", "system"))
    session_id = sha256(scope.encode()).hexdigest()
    response = session.client(
        "bedrock-agentcore",
        config=Config(read_timeout=600, connect_timeout=10, retries={"max_attempts": 0}),
    ).invoke_agent_runtime(
        agentRuntimeArn=arn,
        runtimeSessionId=session_id,
        payload=event.model_dump_json().encode(),
        contentType="application/json",
    )
    stream = response.get("response")
    body = stream.read() if hasattr(stream, "read") else b"".join(stream)
    result = json.loads(body)
    if not isinstance(result, dict):
        raise RuntimeError("AgentCore returned an invalid response")
    return result
