from io import StringIO

from tests.scripts.preflight_stubs import AwsError, StubClient, StubSession, load

preflight = load("preflight_deploy")
findings = load("preflight_findings")
Finding, Status = findings.Finding, findings.Status

CALLER = {"Arn": "arn:aws:iam::123456789012:user/deployer"}
FREE = AwsError("ResourceNotFoundException")


def ready_session() -> StubSession:
    return StubSession(
        {
            "sts": StubClient({"get_caller_identity": CALLER}),
            "ssm": StubClient({"get_parameter": {"Parameter": {"Value": "27"}}}),
            "bedrock": StubClient({"get_inference_profile": {"status": "ACTIVE"}}),
            "bedrock-runtime": StubClient(
                {"converse": {"usage": {"inputTokens": 3, "outputTokens": 1}}}
            ),
            "secretsmanager": StubClient({"describe_secret": FREE}),
            "cloudformation": StubClient({"describe_stacks": AwsError("ValidationError")}),
        }
    )


def test_an_account_with_nothing_in_the_way_has_no_blockers(monkeypatch):
    monkeypatch.setattr(
        preflight.account, "docker", lambda: Finding(check="docker", status=Status.OK, detail="ok")
    )

    collected = preflight.collect(ready_session())

    assert [f for f in collected if f.status is Status.BLOCKER] == []
    assert {f.check for f in collected} >= {"identity", "region", "cdk bootstrap", "docker"}


def test_skipping_inference_spends_nothing_and_asks_no_model(monkeypatch):
    monkeypatch.setattr(
        preflight.account, "docker", lambda: Finding(check="docker", status=Status.OK, detail="ok")
    )
    session = ready_session()

    preflight.collect(session, inference=False)

    assert "bedrock-runtime" not in session.asked


def test_credentials_that_do_not_resolve_stop_the_run_before_any_other_call():
    session = StubSession({"sts": StubClient({"get_caller_identity": AwsError("ExpiredToken")})})

    collected = preflight.collect(session)

    assert len(collected) == 1
    assert session.asked == ["sts"]


def test_a_clean_report_exits_zero_and_says_so():
    stream = StringIO()
    code = preflight.report([Finding(check="identity", status=Status.OK, detail="fine")], stream)

    assert code == 0
    assert preflight.CLEAR in stream.getvalue()


def test_a_blocker_exits_non_zero_and_is_listed_again_at_the_end():
    stream = StringIO()
    blocked = [
        Finding(check="identity", status=Status.OK, detail="fine"),
        Finding(check="cdk bootstrap", status=Status.BLOCKER, detail="absent", remedy="bootstrap"),
        Finding(check="secret repaso/judge", status=Status.WARN, detail="already exists"),
    ]

    code = preflight.report(blocked, stream)
    printed = stream.getvalue()

    assert code == 1
    assert "1 blocker(s), 1 warning(s)" in printed
    assert printed.count("cdk bootstrap") == 2
    assert "-> bootstrap" in printed
