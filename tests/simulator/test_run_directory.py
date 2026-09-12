from repaso.simulator.run_directory import MUST_BE_EMPTY, occupied


def test_a_directory_that_does_not_exist_yet_is_free(tmp_path):
    assert occupied(tmp_path / "never-written") is False


def test_an_empty_directory_is_free(tmp_path):
    (tmp_path / "fresh").mkdir()

    assert occupied(tmp_path / "fresh") is False


def test_a_directory_holding_a_previous_run_is_not(tmp_path):
    used = tmp_path / "used"
    used.mkdir()
    (used / "families.json").write_text("{}", encoding="utf-8")

    assert occupied(used) is True


def test_a_directory_holding_only_a_subdirectory_is_not(tmp_path):
    used = tmp_path / "used"
    (used / "records").mkdir(parents=True)

    assert occupied(used) is True


def test_the_refusal_says_what_to_do_instead():
    assert "empty" in MUST_BE_EMPTY
    assert "previous runs" in MUST_BE_EMPTY
