from repaso.core.harness.bloom import BLOOM_ORDER, bloom_distance, nearest_levels, parse_bloom
from repaso.schemas.item import BloomLevel


def test_the_four_levels_run_from_recall_to_reasoning():
    assert BLOOM_ORDER == (
        BloomLevel.REMEMBER,
        BloomLevel.UNDERSTAND,
        BloomLevel.APPLY,
        BloomLevel.ANALYZE,
    )


def test_a_level_is_read_from_the_word_the_generator_wrote():
    assert parse_bloom("apply") is BloomLevel.APPLY
    assert parse_bloom("  Analyze.  ") is BloomLevel.ANALYZE
    assert parse_bloom("aplicar") is BloomLevel.APPLY


def test_a_word_that_is_not_a_level_is_refused_rather_than_guessed():
    for value in ("", None, "medium", "3", "hard", "evaluate"):
        assert parse_bloom(value) is None


def test_distance_orders_neighbours_before_strangers():
    assert bloom_distance(BloomLevel.REMEMBER, BloomLevel.REMEMBER) == 0
    assert bloom_distance(BloomLevel.REMEMBER, BloomLevel.ANALYZE) == 3
    assert nearest_levels(BloomLevel.APPLY)[0] is BloomLevel.APPLY
    assert nearest_levels(BloomLevel.APPLY)[-1] is BloomLevel.REMEMBER
