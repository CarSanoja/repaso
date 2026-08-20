from pathlib import Path

import pytest

from repaso.core.harness.idempotency import (
    ClaimLedger,
    LocalClaimLedger,
    claim_or_skip,
    job_key,
    update_key,
)

KEY = update_key("chat-1", 42)


def make_ledger(path: Path | None = None) -> LocalClaimLedger:
    return LocalClaimLedger(path=path)


def test_first_claim_wins_and_the_same_owner_loses_on_retry():
    ledger = make_ledger()
    assert ledger.claim(KEY, owner="worker-a") is True
    assert ledger.claim(KEY, owner="worker-a") is False


def test_second_owner_loses_the_race_for_the_same_key():
    ledger = make_ledger()
    ledger.claim(KEY, owner="worker-a")
    assert ledger.claim(KEY, owner="worker-b") is False
    assert ledger.owner_of(KEY) == "worker-a"


def test_owner_of_is_none_for_an_unclaimed_key():
    assert make_ledger().owner_of(KEY) is None


def test_release_allows_a_later_claim_by_another_owner():
    ledger = make_ledger()
    ledger.claim(KEY, owner="worker-a")
    ledger.release(KEY)
    assert ledger.owner_of(KEY) is None
    assert ledger.claim(KEY, owner="worker-b") is True
    assert ledger.owner_of(KEY) == "worker-b"


def test_release_of_an_unclaimed_key_is_a_no_op():
    ledger = make_ledger()
    ledger.release(KEY)
    assert ledger.claim(KEY, owner="worker-a") is True


def test_distinct_keys_are_claimed_independently():
    ledger = make_ledger()
    other = update_key("chat-1", 43)
    assert ledger.claim(KEY, owner="worker-a") is True
    assert ledger.claim(other, owner="worker-b") is True
    assert ledger.owner_of(other) == "worker-b"


def test_claims_replay_from_the_file_into_a_fresh_ledger(tmp_path):
    path = tmp_path / "claims.jsonl"
    first = make_ledger(path)
    first.claim(KEY, owner="worker-a")
    reopened = make_ledger(path)
    assert reopened.owner_of(KEY) == "worker-a"
    assert reopened.claim(KEY, owner="worker-b") is False


def test_replay_keeps_the_owner_of_the_latest_accepted_claim(tmp_path):
    path = tmp_path / "claims.jsonl"
    first = make_ledger(path)
    first.claim(KEY, owner="worker-a")
    first.release(KEY)
    first.claim(KEY, owner="worker-b")
    assert make_ledger(path).owner_of(KEY) == "worker-b"


def test_ledger_reads_a_missing_file_as_empty(tmp_path):
    ledger = make_ledger(tmp_path / "nested" / "claims.jsonl")
    assert ledger.owner_of(KEY) is None


def test_in_memory_ledger_writes_no_file(tmp_path):
    make_ledger().claim(KEY, owner="worker-a")
    assert list(tmp_path.iterdir()) == []


def test_key_derivation_is_stable_for_equivalent_ids():
    assert update_key("chat-1", 42) == update_key("chat-1", "42")
    assert update_key("chat-1", 42) == "update#chat-1#42"
    assert job_key("digest", "student-1", "2026-09-01") == "job#digest#student-1#2026-09-01"


def test_distinct_inputs_never_collide():
    keys = {
        update_key("chat-1", 42),
        update_key("chat-12", 4),
        job_key("digest", "student-1", "2026-09-01"),
        job_key("digest", "student-1", "2026-09-02"),
        job_key("reminder", "student-1", "2026-09-01"),
        job_key("digest-student", "1", "2026-09-01"),
    }
    assert len(keys) == 6


@pytest.mark.parametrize(
    "parts",
    [("digest", "student#1", "2026-09-01"), ("digest", "", "2026-09-01")],
)
def test_key_parts_reject_separators_and_blanks(parts):
    with pytest.raises(ValueError):
        job_key(*parts)


def test_local_ledger_satisfies_the_claim_ledger_protocol():
    assert isinstance(make_ledger(), ClaimLedger)
    assert ClaimLedger not in LocalClaimLedger.__mro__


def test_claim_or_skip_admits_only_the_first_delivery():
    ledger = make_ledger()
    assert claim_or_skip(ledger, KEY, owner="worker-a") is True
    assert claim_or_skip(ledger, KEY, owner="worker-a") is False
    assert claim_or_skip(ledger, update_key("chat-2", 42), owner="worker-a") is True
