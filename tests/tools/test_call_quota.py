from concurrent.futures import ThreadPoolExecutor

import pytest

from repaso.tools.call_quota import DynamoCallQuota, LocalCallQuota, build_call_quota
from tests.tools.test_cloud_recovery import cloud_services as cloud_services

EXPIRES = 1_800_000_000


@pytest.fixture
def quotas(settings, cloud_services) -> dict:
    return {
        "local": LocalCallQuota(settings.local_data_dir / "state"),
        "dynamo": DynamoCallQuota("repaso"),
    }


@pytest.mark.parametrize("backend", ["local", "dynamo"])
def test_a_key_is_granted_exactly_its_limit(quotas, backend):
    quota = quotas[backend]

    granted = [quota.reserve("one-message", 3, EXPIRES) for _ in range(6)]

    assert granted == [True, True, True, False, False, False]
    assert quota.used("one-message") == 3


@pytest.mark.parametrize("backend", ["local", "dynamo"])
def test_separate_keys_do_not_spend_each_other(quotas, backend):
    quota = quotas[backend]

    assert quota.reserve("first", 1, EXPIRES)
    assert not quota.reserve("first", 1, EXPIRES)
    assert quota.reserve("second", 1, EXPIRES)
    assert quota.used("second") == 1


@pytest.mark.parametrize("backend", ["local", "dynamo"])
def test_an_unseen_key_has_spent_nothing(quotas, backend):
    assert quotas[backend].used("never-asked") == 0


def test_concurrent_reservations_never_exceed_the_limit(quotas):
    quota = quotas["local"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        granted = list(pool.map(lambda _: quota.reserve("contended", 5, EXPIRES), range(25)))

    assert sum(granted) == 5
    assert quota.used("contended") == 5


@pytest.mark.parametrize("backend", ["local", "dynamo"])
def test_a_limit_below_one_is_a_programming_error(quotas, backend):
    with pytest.raises(ValueError):
        quotas[backend].reserve("any", 0, EXPIRES)


def test_local_mode_builds_the_file_backed_quota(settings):
    assert isinstance(build_call_quota(settings), LocalCallQuota)


def test_a_deployed_runtime_builds_the_table_backed_quota(settings):
    deployed = settings.model_copy(update={"local_mode": False, "ddb_table": "repaso"})

    assert isinstance(build_call_quota(deployed), DynamoCallQuota)
