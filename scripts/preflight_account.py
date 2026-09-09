"""Whether this account, in this region, can run a repaso deployment at all."""

import subprocess

from preflight_findings import AwsSession, Finding, Status, absent, code_of

from repaso.tools.model_usage import CallUsage, usage_from_response

PROJECT = "repaso"
REGION = "us-east-1"
QUALIFIER = "repaso01"
BOOTSTRAP_PATH = "/cdk-bootstrap"
BOOTSTRAP_PARAMETER = f"{BOOTSTRAP_PATH}/{QUALIFIER}/version"
BOOTSTRAP_FLOOR = 6
PROBE_MODEL = "us.amazon.nova-micro-v1:0"
MODELS = (
    "us.anthropic.claude-sonnet-4-6",
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "us.amazon.nova-lite-v1:0",
    PROBE_MODEL,
)
BOOTSTRAP_REMEDY = (
    f"npx aws-cdk@2 bootstrap --qualifier {QUALIFIER} "
    f"--toolkit-stack-name CDKToolkit-{PROJECT} aws://<account>/{REGION}"
)
CREDENTIAL_REMEDY = "export AWS_PROFILE to the authorized profile and refresh it"
MODEL_REMEDY = "request access to the inference profile in the Bedrock console"
THROUGHPUT_REMEDY = "on-demand throughput must answer before a family is enrolled"
DOCKER_REMEDY = "start Docker; both images are built on the deploying machine"


def identity(session: AwsSession) -> Finding:
    try:
        caller = session.client("sts").get_caller_identity()
    except Exception as error:
        return Finding(
            check="identity",
            status=Status.BLOCKER,
            detail=f"no usable credentials: {code_of(error)}",
            remedy=CREDENTIAL_REMEDY,
        )
    return Finding(check="identity", status=Status.OK, detail=str(caller["Arn"]))


def region(session: AwsSession) -> Finding:
    found = session.region_name
    if found == REGION:
        return Finding(check="region", status=Status.OK, detail=found)
    return Finding(
        check="region",
        status=Status.BLOCKER,
        detail=f"session resolves {found!r}; every stack pins {REGION}",
        remedy=f"export AWS_REGION={REGION}",
    )


def other_qualifiers(client) -> list[str]:
    try:
        answer = client.get_parameters_by_path(Path=BOOTSTRAP_PATH, Recursive=True)
    except Exception:
        return []
    names = (str(entry.get("Name", "")) for entry in answer.get("Parameters", []))
    found = {name.split("/")[2] for name in names if name.count("/") >= 2}
    return sorted(found - {QUALIFIER})


def bootstrap(session: AwsSession) -> Finding:
    client = session.client("ssm")
    try:
        found = client.get_parameter(Name=BOOTSTRAP_PARAMETER)
    except Exception as error:
        if absent(error):
            others = other_qualifiers(client)
            elsewhere = f", though {', '.join(others)} is" if others else ""
            return Finding(
                check="cdk bootstrap",
                status=Status.BLOCKER,
                detail=f"{BOOTSTRAP_PARAMETER} does not exist{elsewhere}",
                remedy=BOOTSTRAP_REMEDY,
            )
        return Finding(
            check="cdk bootstrap",
            status=Status.WARN,
            detail=f"cannot read {BOOTSTRAP_PARAMETER}: {code_of(error)}",
        )
    version = str(found["Parameter"]["Value"])
    current = version.isdigit() and int(version) >= BOOTSTRAP_FLOOR
    return Finding(
        check="cdk bootstrap",
        status=Status.OK if current else Status.BLOCKER,
        detail=f"qualifier {QUALIFIER} at version {version}",
        remedy="" if current else BOOTSTRAP_REMEDY,
    )


def models(session: AwsSession) -> list[Finding]:
    client = session.client("bedrock")
    findings: list[Finding] = []
    for model in MODELS:
        try:
            profile = client.get_inference_profile(inferenceProfileIdentifier=model)
        except Exception as error:
            findings.append(
                Finding(
                    check=f"model {model}",
                    status=Status.BLOCKER,
                    detail=f"not reachable: {code_of(error)}",
                    remedy=MODEL_REMEDY,
                )
            )
            continue
        findings.append(
            Finding(check=f"model {model}", status=Status.OK, detail=str(profile["status"]))
        )
    return findings


def inference(session: AwsSession) -> Finding:
    try:
        answer = session.client("bedrock-runtime").converse(
            modelId=PROBE_MODEL,
            messages=[{"role": "user", "content": [{"text": "ok"}]}],
            inferenceConfig={"maxTokens": 4, "temperature": 0},
        )
    except Exception as error:
        return Finding(
            check="bedrock inference",
            status=Status.BLOCKER,
            detail=f"{PROBE_MODEL} refused: {code_of(error)}",
            remedy=THROUGHPUT_REMEDY,
        )
    counted = usage_from_response(answer) or CallUsage()
    return Finding(
        check="bedrock inference",
        status=Status.OK,
        detail=f"{PROBE_MODEL} answered in {counted.input_tokens}/{counted.output_tokens} tokens",
    )


def docker(run=subprocess.run) -> Finding:
    command = ["docker", "version", "--format", "{{.Server.Os}}/{{.Server.Arch}}"]
    try:
        result = run(command, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as error:
        detail = type(error).__name__
    else:
        if result.returncode == 0:
            return Finding(check="docker", status=Status.OK, detail=result.stdout.strip())
        detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "no daemon"
    return Finding(
        check="docker", status=Status.BLOCKER, detail=detail, remedy=DOCKER_REMEDY
    )
