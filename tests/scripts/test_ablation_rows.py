import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from ablation_arms import ADVISORY_PROBE, CRITIC_ONLY, FORCED_CHOICE_VETO  # noqa: E402
from ablation_items import LABEL_SOURCE, OPTION_CUE, WRONG_KEY  # noqa: E402
from ablation_rows import COLUMNS, observations, read_rows, write_rows  # noqa: E402

from tests.scripts.ablation_fakes import frozen_item, review  # noqa: E402


def rows_for(**kwargs):
    item = frozen_item(kwargs.pop("item_id", "it-1"), kwargs.pop("defect", "none"))
    rows = observations(review(item.item_id, **kwargs), item, LABEL_SOURCE)
    return {row.arm: row for row in rows}


def test_every_review_yields_one_row_per_arm():
    rows = rows_for()
    assert set(rows) == {CRITIC_ONLY, FORCED_CHOICE_VETO, ADVISORY_PROBE}
    assert all(row.label_source == LABEL_SOURCE for row in rows.values())
    assert all(row.independent_reviewer == "none" for row in rows.values())


def test_each_arm_carries_only_the_calls_that_arm_would_have_made():
    rows = rows_for()
    assert rows[CRITIC_ONLY].input_tokens == 900
    assert rows[FORCED_CHOICE_VETO].input_tokens == 1020
    assert rows[ADVISORY_PROBE].input_tokens == 990
    assert rows[CRITIC_ONLY].latency_ms == 1000.0
    assert rows[ADVISORY_PROBE].latency_ms == 1400.0


def test_the_probe_answer_is_kept_next_to_the_arm_that_asked_for_it():
    rows = rows_for(forced_hit=True, advisory_hit=False)
    assert rows[CRITIC_ONLY].probe_choice == ""
    assert rows[FORCED_CHOICE_VETO].probe_choice == "2/4"
    assert rows[ADVISORY_PROBE].probe_choice == "UNKNOWN"
    assert not rows[FORCED_CHOICE_VETO].accepted
    assert rows[ADVISORY_PROBE].accepted


def test_a_row_says_whether_the_key_it_finalized_was_the_planted_wrong_one():
    assert rows_for(defect=WRONG_KEY)[CRITIC_ONLY].key_correct is False
    assert rows_for(defect=OPTION_CUE)[CRITIC_ONLY].key_correct is True


def test_the_capture_file_keeps_the_pre_registered_columns_and_reads_back(tmp_path):
    item = frozen_item("it-1")
    rows = observations(review("it-1", forced_hit=True), item, LABEL_SOURCE)
    path = tmp_path / "ablation_observations.csv"
    write_rows(path, rows)
    assert path.read_text(encoding="utf-8").splitlines()[0] == ",".join(COLUMNS)
    assert read_rows(path) == rows
