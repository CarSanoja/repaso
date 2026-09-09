import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import teardown  # noqa: E402
from teardown_plan import UNKNOWN, build_plan  # noqa: E402

PROJECT = "repaso"
STACKS = ("foundation", "messaging", "guardrails", "api", "agentcore", "observability")
REVERSED = ("observability", "agentcore", "api", "guardrails", "messaging", "foundation")
RETAINED = [
    ("AWS::KMS::Key", "1a2b3c4d"),
    ("AWS::S3::Bucket", "repaso-foundation-mediabucket-abc"),
    ("AWS::DynamoDB::Table", "repaso"),
]
ALREADY_IN_THE_ACCOUNT = (
    ("stack", "quanta-prod-app"),
    ("bucket", "quanta-prod-files"),
    ("bucket", "quanta-tfstate-000000000000"),
    ("secret", "quanta/prod/telegram"),
    ("log group", "/aws/lambda/quanta-prod-slack-notifier"),
)


def tagged(mode: str = "durable") -> dict[str, str]:
    return {"project": PROJECT, "managed-by": "cdk", "deployment-mode": mode}


class FakeReader:
    def __init__(self, stacks=(), buckets=(), secrets=(), log_groups=(), retained=()) -> None:
        self._stacks = list(stacks)
        self._buckets = list(buckets)
        self._secrets = list(secrets)
        self._log_groups = list(log_groups)
        self._retained = list(retained)

    def stacks(self):
        return self._stacks

    def buckets(self):
        return self._buckets

    def secrets(self):
        return self._secrets

    def log_groups(self):
        return self._log_groups

    def retained_resources(self, stack):
        return self._retained if stack == f"{PROJECT}-foundation" else []


def deployed(mode: str = "durable") -> FakeReader:
    return FakeReader(
        stacks=[(f"{PROJECT}-{name}", tagged(mode)) for name in STACKS],
        buckets=[("repaso-foundation-mediabucket-abc", tagged(mode))],
        secrets=[("repaso/telegram", tagged(mode))],
        log_groups=[("/aws/lambda/repaso-webhook", tagged(mode))],
        retained=RETAINED if mode == "durable" else (),
    )


def test_an_account_with_none_of_this_deployment_has_nothing_to_remove():
    plan = build_plan(FakeReader())

    assert plan.empty
    assert not plan.blocked
    assert plan.mode == UNKNOWN
    assert teardown.report(plan, applying=False)[-1] == teardown.NOTHING


def test_the_stacks_come_off_in_the_reverse_of_the_order_they_went_on():
    plan = build_plan(deployed())

    assert [target.name for target in plan.stacks] == [f"{PROJECT}-{n}" for n in REVERSED]


def test_durable_removes_the_stacks_and_keeps_what_holds_family_data():
    plan = build_plan(deployed("durable"))

    assert {target.kind for target in plan.removes} == {"stack"}
    assert {target.kind for target in plan.keeps} == {"retained", "bucket", "secret", "log group"}
    assert [target.name for target in plan.keeps if target.kind == "retained"] == [
        physical for _, physical in RETAINED
    ]


def test_ephemeral_removes_the_storage_that_cloudformation_leaves_behind():
    plan = build_plan(deployed("ephemeral"))

    assert {target.kind for target in plan.removes} == {"stack", "bucket", "secret", "log group"}
    assert plan.erases_data
    assert plan.keeps == ()


@pytest.mark.parametrize("kind,name", ALREADY_IN_THE_ACCOUNT)
def test_a_tagged_resource_outside_the_prefix_stops_the_whole_run(kind, name):
    field = {"stack": "stacks", "bucket": "buckets", "secret": "secrets"}.get(kind, "log_groups")
    plan = build_plan(FakeReader(**{field: [(name, tagged())]}))

    assert plan.blocked
    assert any("outside the repaso namespace" in line for line in plan.refusals)


def test_a_resource_inside_the_prefix_without_the_tag_stops_the_whole_run():
    plan = build_plan(FakeReader(buckets=[("repaso-stray", {"owner": "someone else"})]))

    assert plan.blocked
    assert "carries no project=repaso tag" in plan.refusals[0]


def test_stacks_that_disagree_about_the_mode_stop_the_whole_run():
    plan = build_plan(
        FakeReader(
            stacks=[
                (f"{PROJECT}-foundation", tagged("durable")),
                (f"{PROJECT}-api", tagged("ephemeral")),
            ]
        )
    )

    assert plan.blocked
    assert plan.mode == UNKNOWN


def test_an_unknown_mode_never_reaches_the_storage():
    plan = build_plan(FakeReader(buckets=[("repaso-orphan", {"project": PROJECT})]))

    assert plan.mode == UNKNOWN
    assert plan.removes == ()
    assert teardown.UNKNOWN_MODE_NOTE in teardown.report(plan, applying=False)


def test_a_blocked_plan_reports_only_the_refusals():
    plan = build_plan(FakeReader(buckets=[("quanta-prod-files", tagged())]))
    lines = teardown.report(plan, applying=False)

    assert lines[1] == "refusing to continue:"
    assert not [line for line in lines if "would remove" in line]


def test_the_dry_run_is_what_you_get_when_you_ask_for_nothing():
    assert teardown.parse([]).apply is False
    assert teardown.parse(["--apply"]).apply is True
