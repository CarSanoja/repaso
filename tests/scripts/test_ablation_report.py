import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from ablation_arms import ADVISORY_PROBE, CRITIC_ONLY, FORCED_CHOICE_VETO  # noqa: E402
from ablation_items import IMPLAUSIBLE_DISTRACTORS, LABEL_SOURCE, NO_DEFECT  # noqa: E402
from ablation_report import build_report, rate, wilson  # noqa: E402
from ablation_rows import observations  # noqa: E402

from tests.scripts.ablation_fakes import frozen_item, review  # noqa: E402


def dataset():
    clean = [frozen_item(f"clean-{number}") for number in range(3)]
    planted = [
        frozen_item(f"planted-{number}", IMPLAUSIBLE_DISTRACTORS, clue=True) for number in range(2)
    ]
    reviews = [
        review("clean-0", critic_accepted=True, forced_hit=True),
        review("clean-1", critic_accepted=True),
        review("clean-2", critic_accepted=False),
        review("planted-0", critic_accepted=False, forced_hit=True, advisory_hit=True),
        review("planted-1", critic_accepted=True, advisory_hit=True, repeat=False),
    ]
    items = {item.item_id: item for item in clean + planted}
    rows = [
        row
        for entry in reviews
        for row in observations(entry, items[entry.item_id], LABEL_SOURCE)
    ]
    return rows, reviews, clean + planted


def test_retention_and_rejection_use_the_construction_denominators_not_all_items():
    report = build_report(*dataset())
    assert report["labels"] == {
        "items": 5,
        "unplanted": 3,
        "planted": 2,
        "planted_option_clue": 2,
        "by_defect": {IMPLAUSIBLE_DISTRACTORS: 2, NO_DEFECT: 3},
    }
    critic = report["arms"][CRITIC_ONLY]
    assert critic["unplanted_retention"]["of"] == 3
    assert critic["unplanted_retention"]["count"] == 2
    assert critic["planted_rejection"]["of"] == 2
    assert critic["planted_rejection"]["count"] == 1


def test_the_veto_arm_loses_a_clean_item_the_probe_happened_to_answer():
    report = build_report(*dataset())
    assert report["arms"][FORCED_CHOICE_VETO]["unplanted_retention"]["count"] == 1
    assert report["arms"][ADVISORY_PROBE]["unplanted_retention"]["count"] == 2


def test_key_correctness_is_scored_over_what_the_arm_accepted():
    report = build_report(*dataset())
    assert report["arms"][CRITIC_ONLY]["finalized_key_correctness"]["of"] == 3
    assert report["arms"][FORCED_CHOICE_VETO]["finalized_key_correctness"]["of"] == 2


def test_each_probe_arm_costs_one_extra_call_per_decision():
    report = build_report(*dataset())
    assert report["arms"][CRITIC_ONLY]["calls_per_decision"] == 1.0
    assert report["arms"][ADVISORY_PROBE]["calls_per_decision"] == 2.0
    assert report["arms"][ADVISORY_PROBE]["extra_calls_vs_critic_only"] == 5


def test_the_probe_signal_is_split_by_whether_a_clue_was_planted():
    signal = build_report(*dataset())["probe_signal"]["advisory"]
    assert signal["hit_rate_on_planted_clue"] == {
        "count": 2,
        "of": 2,
        "rate": 1.0,
        "wilson_95": wilson(2, 2),
    }
    assert signal["hit_rate_without_planted_clue"]["count"] == 0


def test_a_rate_over_nothing_is_reported_as_nothing():
    assert rate(0, 0) == {"count": 0, "of": 0, "rate": None, "wilson_95": None}
