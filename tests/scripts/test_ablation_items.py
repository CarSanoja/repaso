import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from ablation_items import (  # noqa: E402
    ABSURD_OPTIONS,
    CUE_SUFFIX,
    IMPLAUSIBLE_DISTRACTORS,
    NO_DEFECT,
    OPTION_CUE,
    WRONG_KEY,
    as_item,
    freeze,
    key_planted_wrong,
    plant_for,
    presented_options,
)

from repaso.schemas.common import CompetencyId, ItemId  # noqa: E402
from repaso.schemas.item import Item, ItemKind  # noqa: E402
from repaso.schemas.provenance import Provenance, Source  # noqa: E402

NOW = datetime(2026, 9, 12, tzinfo=UTC)
PROVENANCE = Provenance(source=Source.GENERATED, created_at=NOW)
PAGE = "demo/cuaderno-fracciones.png"


def item(number: int) -> Item:
    return Item(
        id=ItemId(f"it-{number:02d}"),
        competency_id=CompetencyId("math.g4.fractions.equivalence"),
        kind=ItemKind.MCQ,
        difficulty=2,
        stem=f"¿Cuál fracción es equivalente a 1/{number + 2}?",
        options=[f"{number}/4", f"{number}/5", f"{number}/6"],
        answer_key=f"{number}/4",
        rationale="El cuaderno multiplica arriba y abajo por el mismo número.",
        provenance=PROVENANCE,
    )


def thirty() -> list[Item]:
    return [item(number) for number in range(30)]


def test_two_of_every_five_items_carry_a_planted_defect():
    kinds = [plant_for(index) for index in range(30)]
    assert kinds.count(NO_DEFECT) == 18
    assert kinds.count(WRONG_KEY) == 4
    assert kinds.count(IMPLAUSIBLE_DISTRACTORS) == 4
    assert kinds.count(OPTION_CUE) == 4


def test_a_moved_key_names_an_option_that_is_not_the_generated_one():
    planted = [row for row in freeze(thirty(), PAGE) if row.defect == WRONG_KEY]
    assert len(planted) == 4
    for row in planted:
        assert row.answer_key in row.options
        assert row.answer_key != row.generated_answer_key
        assert key_planted_wrong(row)


def test_implausible_distractors_replace_every_option_except_the_key():
    planted = [row for row in freeze(thirty(), PAGE) if row.defect == IMPLAUSIBLE_DISTRACTORS]
    for row in planted:
        assert row.answer_key == row.generated_answer_key
        others = [option for option in row.options if option != row.answer_key]
        assert set(others) <= set(ABSURD_OPTIONS)
        assert row.construction_option_clue


def test_the_cue_plant_lengthens_the_key_and_leaves_the_distractors_alone():
    planted = [row for row in freeze(thirty(), PAGE) if row.defect == OPTION_CUE]
    for row in planted:
        assert row.answer_key == row.generated_answer_key + CUE_SUFFIX
        assert row.answer_key in row.options
        assert max(row.options, key=len) == row.answer_key
        assert not key_planted_wrong(row)


def test_unplanted_items_keep_what_was_generated_and_are_labeled_as_unplanted():
    clean = [row for row in freeze(thirty(), PAGE) if row.defect == NO_DEFECT]
    assert len(clean) == 18
    for row in clean:
        assert row.options == row.generated_options
        assert row.answer_key == row.generated_answer_key
        assert row.construction_valid
        assert not row.construction_option_clue


def test_a_permutation_is_a_reordering_that_the_seed_alone_decides():
    frozen = freeze(thirty(), PAGE)
    first = [presented_options(row, 1) for row in frozen]
    assert first == [presented_options(row, 1) for row in frozen]
    pairs = zip(first, frozen, strict=True)
    assert all(sorted(order) == sorted(row.options) for order, row in pairs)
    second = [presented_options(row, 2) for row in frozen]
    assert first != second


def test_the_item_the_critic_reads_carries_the_permuted_options():
    row = freeze(thirty(), PAGE)[0]
    options = presented_options(row, 3)
    built = as_item(row, options, NOW, "model-under-test")
    assert built.options == options
    assert built.answer_key == row.answer_key
    assert built.kind is ItemKind.MCQ
