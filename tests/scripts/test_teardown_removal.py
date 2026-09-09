import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import teardown  # noqa: E402
from teardown_plan import Plan, Target  # noqa: E402
from teardown_remover import BotoRemover, OutsideNamespace  # noqa: E402

PROJECT = "repaso"
TAGGED = (("project", PROJECT),)
BUCKET = "repaso-foundation-mediabucket-abc"


class FakePaginator:
    def __init__(self, pages) -> None:
        self.pages = pages

    def paginate(self, **kwargs):
        return self.pages


class FakeS3:
    def __init__(self, pages) -> None:
        self.pages = pages
        self.deleted: list[dict] = []

    def get_paginator(self, name):
        return FakePaginator(self.pages)

    def delete_objects(self, **kwargs):
        self.deleted.append(kwargs)
        return {}


class FakeSecrets:
    class exceptions:
        class ResourceNotFoundException(Exception):
            pass

        class InvalidRequestException(Exception):
            pass

    def __init__(self, raises=None) -> None:
        self.raises = raises
        self.calls: list[dict] = []

    def delete_secret(self, **kwargs):
        if self.raises is not None:
            raise self.raises
        self.calls.append(kwargs)
        return {}


class FakeSession:
    def __init__(self, s3=None, secretsmanager=None) -> None:
        self.clients = {"s3": s3, "secretsmanager": secretsmanager}

    def client(self, name):
        return self.clients.get(name) or object()


def remover(s3=None, secretsmanager=None) -> BotoRemover:
    return BotoRemover(FakeSession(s3, secretsmanager), PROJECT)


def versions(count: int) -> list[dict]:
    return [
        {
            "Versions": [{"Key": f"media/{i}.jpg", "VersionId": f"v{i}"} for i in range(count)],
            "DeleteMarkers": [{"Key": "media/gone.jpg", "VersionId": "vm"}],
        }
    ]


@pytest.mark.parametrize(
    "target",
    [
        Target("bucket", "quanta-prod-files", tags=TAGGED),
        Target("stack", "quanta-prod-app", tags=TAGGED),
        Target("secret", "quanta/prod/telegram", tags=TAGGED),
    ],
)
def test_a_target_outside_the_prefix_is_never_touched(target):
    with pytest.raises(OutsideNamespace, match="outside the repaso namespace"):
        remover().verify(target)


def test_a_target_inside_the_prefix_without_the_tag_is_never_touched():
    with pytest.raises(OutsideNamespace, match="carries no project=repaso"):
        remover().verify(Target("bucket", BUCKET, tags=(("owner", "someone else"),)))


def test_a_kind_the_teardown_does_not_understand_is_never_touched():
    with pytest.raises(OutsideNamespace, match="not a kind"):
        remover().verify(Target("retained", "repaso", tags=TAGGED))


def test_emptying_a_bucket_removes_its_versions_and_its_delete_markers():
    s3 = FakeS3(versions(3))
    message = remover(s3).empty(Target("bucket", BUCKET, tags=TAGGED))

    keys = [entry["VersionId"] for call in s3.deleted for entry in call["Delete"]["Objects"]]
    assert keys == ["v0", "v1", "v2", "vm"]
    assert message == "emptied 4 object version(s)"


def test_emptying_sends_no_request_for_an_empty_bucket():
    s3 = FakeS3([{}])
    message = remover(s3).empty(Target("bucket", BUCKET, tags=TAGGED))

    assert s3.deleted == []
    assert message == "emptied 0 object version(s)"


def test_an_untagged_bucket_is_not_emptied_either():
    s3 = FakeS3(versions(1))

    with pytest.raises(OutsideNamespace):
        remover(s3).empty(Target("bucket", BUCKET))

    assert s3.deleted == []


def test_a_secret_goes_without_a_recovery_window_so_its_name_is_reusable():
    secrets = FakeSecrets()
    target = Target("secret", "repaso/telegram", tags=TAGGED)
    message = remover(secretsmanager=secrets).remove(target)

    assert secrets.calls == [{"SecretId": "repaso/telegram", "ForceDeleteWithoutRecovery": True}]
    assert message == "deleted without a recovery window"


def test_a_secret_already_inside_a_window_is_reported_rather_than_forced():
    secrets = FakeSecrets(raises=FakeSecrets.exceptions.InvalidRequestException())
    target = Target("secret", "repaso/telegram", tags=TAGGED)

    assert "stays reserved" in remover(secretsmanager=secrets).remove(target)


def test_a_secret_that_is_gone_is_not_an_error():
    secrets = FakeSecrets(raises=FakeSecrets.exceptions.ResourceNotFoundException())
    target = Target("secret", "repaso/judge", tags=TAGGED)

    assert remover(secretsmanager=secrets).remove(target) == "already gone"


def test_the_operator_has_to_type_the_phrase_the_prompt_asks_for():
    plan = Plan(project=PROJECT, mode="ephemeral", stacks=(Target("stack", "repaso-api"),))

    assert teardown.confirmed(plan, io.StringIO("remove repaso\n"))
    assert not teardown.confirmed(plan, io.StringIO("yes\n"))
    assert not teardown.confirmed(plan, io.StringIO(""))
