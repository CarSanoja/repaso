from subprocess import CompletedProcess

import pytest

from tests.scripts.preflight_stubs import AwsError, StubClient, StubSession, load

account = load("preflight_account")
Status = load("preflight_findings").Status

CALLER = {"Arn": "arn:aws:iam::123456789012:user/deployer"}
PROFILE = {"status": "ACTIVE"}
ANSWER = {"usage": {"inputTokens": 3, "outputTokens": 1}}


def session(**clients) -> StubSession:
    return StubSession({name: StubClient(answers) for name, answers in clients.items()})


def test_credentials_that_do_not_resolve_block_everything():
    found = account.identity(session(sts={"get_caller_identity": AwsError("ExpiredToken")}))

    assert found.status is Status.BLOCKER
    assert "ExpiredToken" in found.detail
    assert found.remedy


def test_a_working_caller_is_reported_by_its_arn():
    found = account.identity(session(sts={"get_caller_identity": CALLER}))

    assert found.status is Status.OK
    assert found.detail == CALLER["Arn"]


def test_a_session_in_another_region_blocks():
    elsewhere = StubSession({}, region_name="eu-west-1")

    assert account.region(elsewhere).status is Status.BLOCKER
    assert account.region(StubSession({})).status is Status.OK


def test_an_account_with_no_bootstrap_says_which_command_makes_one():
    found = account.bootstrap(session(ssm={"get_parameter": AwsError("ParameterNotFound")}))

    assert found.status is Status.BLOCKER
    assert account.QUALIFIER in found.remedy
    assert "bootstrap" in found.remedy


@pytest.mark.parametrize(
    ("version", "status"), [("6", Status.OK), ("21", Status.OK), ("5", Status.BLOCKER)]
)
def test_a_bootstrap_older_than_the_synthesizer_needs_blocks(version, status):
    ssm = {"get_parameter": {"Parameter": {"Value": version}}}

    assert account.bootstrap(session(ssm=ssm)).status is status


def test_every_configured_model_is_probed_and_a_missing_one_blocks():
    def profile(inferenceProfileIdentifier: str):
        if inferenceProfileIdentifier == account.PROBE_MODEL:
            raise AwsError("ResourceNotFoundException")
        return PROFILE

    found = account.models(session(bedrock={"get_inference_profile": profile}))

    assert len(found) == len(account.MODELS)
    assert [f.status for f in found].count(Status.BLOCKER) == 1
    assert account.PROBE_MODEL in found[-1].check


def test_inference_that_is_refused_is_a_blocker_with_the_service_code():
    refused = session(**{"bedrock-runtime": {"converse": AwsError("AccessDeniedException")}})
    found = account.inference(refused)

    assert found.status is Status.BLOCKER
    assert "AccessDeniedException" in found.detail


def test_inference_that_answers_reports_what_it_cost():
    reached = session(**{"bedrock-runtime": {"converse": ANSWER}})

    assert account.inference(reached).status is Status.OK
    assert "3/1" in account.inference(reached).detail


def test_a_probe_never_asks_for_more_than_four_tokens():
    client = StubClient({"converse": ANSWER})
    account.inference(StubSession({"bedrock-runtime": client}))

    assert client.calls[0][1]["inferenceConfig"]["maxTokens"] == 4


def test_docker_without_a_daemon_blocks():
    def run(command, **kwargs):
        return CompletedProcess(command, 1, stdout="", stderr="Cannot connect to the daemon")

    found = account.docker(run=run)

    assert found.status is Status.BLOCKER
    assert "daemon" in found.detail


def test_docker_that_answers_reports_its_platform():
    def run(command, **kwargs):
        return CompletedProcess(command, 0, stdout="linux/arm64\n", stderr="")

    assert account.docker(run=run) == account.Finding(
        check="docker", status=Status.OK, detail="linux/arm64"
    )


def test_a_machine_without_the_docker_binary_blocks():
    def run(command, **kwargs):
        raise FileNotFoundError(command[0])

    assert account.docker(run=run).status is Status.BLOCKER
