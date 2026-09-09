import pytest

from tests.infra.namespace_fixtures import (
    ALREADY_IN_THE_ACCOUNT,
    bucket_policy_with,
    found,
    rendered,
    role_with,
)

ESCAPE_ROUTES = (
    ("AWS::SSM::Parameter", {"Name": "/quanta/prod/config"}),
    ("AWS::SecretsManager::Secret", {"Name": "quanta/prod/telegram"}),
    ("AWS::Logs::LogGroup", {"LogGroupName": "/aws/lambda/quanta-prod-slack-notifier"}),
    ("AWS::Scheduler::ScheduleGroup", {"Name": "quanta-prod"}),
    ("AWS::SQS::Queue", {"QueueName": "quanta-prod-work"}),
    (
        "AWS::Lambda::Function",
        {
            "FunctionName": "repaso-webhook",
            "Environment": {"Variables": {"REPASO_MEDIA_BUCKET": "quanta-prod-files"}},
        },
    ),
    (
        "AWS::Lambda::EventSourceMapping",
        {"EventSourceArn": {"Fn::ImportValue": "quanta-prod-network:QueueArn"}},
    ),
)

EVERYONE = {
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::repaso-material/*",
}


@pytest.mark.parametrize("resource", ALREADY_IN_THE_ACCOUNT)
def test_a_name_that_already_exists_in_the_account_is_refused(tmp_path, resource):
    assert found(rendered(tmp_path, [resource]))


@pytest.mark.parametrize("resource", ESCAPE_ROUTES)
def test_every_other_way_of_naming_something_outside_is_refused(tmp_path, resource):
    assert found(rendered(tmp_path, [resource]))


def test_a_resource_inside_the_namespace_passes(tmp_path):
    templates = rendered(
        tmp_path,
        [
            ("AWS::S3::Bucket", {"BucketName": "repaso-extra"}),
            ("AWS::SSM::Parameter", {"Name": "/repaso/extra"}),
            ("AWS::SecretsManager::Secret", {"Name": "repaso/extra"}),
            ("AWS::Logs::LogGroup", {"LogGroupName": "/aws/lambda/repaso-extra"}),
        ],
    )

    assert found(templates) == []


def test_a_policy_may_not_reach_a_bucket_this_project_does_not_own(tmp_path):
    templates = role_with(
        tmp_path,
        {
            "Effect": "Allow",
            "Action": ["s3:GetObject"],
            "Resource": ["arn:aws:s3:::quanta-prod-files/*"],
        },
    )

    assert found(templates)


def test_a_declared_action_still_may_not_name_a_foreign_log_group(tmp_path):
    templates = role_with(
        tmp_path,
        {
            "Effect": "Allow",
            "Action": ["logs:DescribeLogGroups"],
            "Resource": [
                {
                    "Fn::Sub": "arn:aws:logs:us-east-1:${AWS::AccountId}"
                    ":log-group:/aws/lambda/quanta-prod-slack-notifier"
                }
            ],
        },
    )

    assert found(templates)


def test_the_declared_service_wide_grants_the_runtime_needs_are_allowed(tmp_path):
    templates = role_with(
        tmp_path,
        {
            "Effect": "Allow",
            "Action": ["logs:DescribeLogGroups"],
            "Resource": [
                {"Fn::Sub": "arn:aws:logs:us-east-1:${AWS::AccountId}:log-group:*"}
            ],
        },
    )

    assert found(templates) == []


def test_listing_the_schedules_it_owns_is_a_declared_service_wide_grant(tmp_path):
    templates = role_with(
        tmp_path, {"Effect": "Allow", "Action": ["scheduler:ListSchedules"], "Resource": "*"}
    )

    assert found(templates) == []


def test_an_action_nobody_declared_may_not_run_against_everything(tmp_path):
    templates = role_with(
        tmp_path, {"Effect": "Allow", "Action": ["s3:DeleteBucket"], "Resource": "*"}
    )

    assert found(templates)


def test_a_refusal_aimed_at_everyone_is_not_a_trust(tmp_path):
    statement = {
        **EVERYONE,
        "Effect": "Deny",
        "Condition": {"Bool": {"aws:SecureTransport": "false"}},
    }

    assert found(bucket_policy_with(tmp_path, statement)) == []


def test_a_grant_aimed_at_everyone_is_still_refused(tmp_path):
    assert found(bucket_policy_with(tmp_path, {**EVERYONE, "Effect": "Allow"}))
