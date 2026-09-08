import pytest

from tests.scripts.preflight_stubs import AwsError, StubClient, StubSession, load

names = load("preflight_names")
Status = load("preflight_findings").Status

FREE = AwsError("ResourceNotFoundException")


def session(**clients) -> StubSession:
    return StubSession({name: StubClient(answers) for name, answers in clients.items()})


def test_an_empty_account_reports_every_secret_as_the_stack_will_create_it():
    found = names.secrets(session(secretsmanager={"describe_secret": FREE}))

    assert [finding.status for finding in found] == [Status.OK] * len(names.SECRETS)


def test_a_secret_already_standing_warns_that_the_stack_will_not_own_it():
    found = names.secrets(session(secretsmanager={"describe_secret": {}}))

    assert {finding.status for finding in found} == {Status.WARN}
    assert all(finding.remedy for finding in found)


def test_a_secret_inside_its_deletion_window_blocks_the_name_it_still_holds():
    scheduled = {"describe_secret": {"DeletedDate": "2026-09-30T00:00:00Z"}}
    found = names.secrets(session(secretsmanager=scheduled))

    assert {finding.status for finding in found} == {Status.BLOCKER}
    assert "restore-secret" in found[0].remedy


def test_names_nothing_holds_produce_no_findings():
    free = {service: {method: FREE} for service, method, _ in names.NAMED}

    assert names.taken(session(**free)) == []


def test_a_name_the_stacks_want_and_something_already_has_blocks():
    held = {service: {method: {}} for service, method, _ in names.NAMED}
    found = names.taken(session(**held))

    assert len(found) == len(names.NAMED)
    assert {finding.status for finding in found} == {Status.BLOCKER}


def test_a_name_the_caller_may_not_read_is_a_warning_and_not_a_verdict():
    opaque = {service: {method: AwsError("AccessDenied")} for service, method, _ in names.NAMED}
    found = names.taken(session(**opaque))

    assert {finding.status for finding in found} == {Status.WARN}


def test_a_probe_that_fails_for_an_unexpected_reason_is_not_swallowed():
    broken = {"dynamodb": StubClient({"describe_table": AwsError("ThrottlingException")})}

    with pytest.raises(AwsError):
        names.taken(StubSession(broken))


def test_an_account_with_no_repaso_stacks_reports_a_first_deployment():
    empty = session(cloudformation={"describe_stacks": AwsError("ValidationError")})

    assert names.stacks(empty) == []


def test_stacks_that_already_stand_say_the_run_is_an_update():
    found = names.stacks(session(cloudformation={"describe_stacks": {}}))

    assert len(found) == len(names.STACKS)
    assert all(finding.status is Status.WARN for finding in found)
