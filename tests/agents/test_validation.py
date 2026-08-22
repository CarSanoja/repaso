from datetime import UTC, datetime

from repaso.agents.answerability_probe import (
    combine,
    probe_blind,
    rejection_rate,
    render_blind,
)
from repaso.agents.item_critic import CRITIC_ERROR_NOTE, critique
from repaso.schemas.common import CompetencyId, ItemId
from repaso.schemas.item import Item, ItemFlaw, ItemKind, ItemVerdict
from repaso.schemas.provenance import Provenance, Source
from repaso.tools.llm import LocalPlaybackModel

PROVENANCE = Provenance(source=Source.GENERATED, created_at=datetime(2026, 3, 1, tzinfo=UTC))
OPTIONS = ["La respiración", "La fotosíntesis", "La digestión"]
SOURCE = "Las plantas fabrican su alimento con la luz del sol mediante la fotosíntesis."


def mcq(item_id: str = "it-1", answer_key: str = "La fotosíntesis") -> Item:
    return Item(
        id=ItemId(item_id),
        competency_id=CompetencyId("cn-4-01"),
        kind=ItemKind.MCQ,
        difficulty=2,
        stem="¿Qué proceso usan las plantas para fabricar su alimento?",
        options=OPTIONS,
        answer_key=answer_key,
        rationale="El material lo explica en la primera línea.",
        provenance=PROVENANCE,
    )


def open_item() -> Item:
    return Item(
        id=ItemId("it-2"),
        competency_id=CompetencyId("cn-4-01"),
        kind=ItemKind.OPEN,
        difficulty=3,
        stem="Explica con tus palabras para qué le sirve la luz del sol a una planta.",
        answer_key="Para fabricar su alimento.",
        rationale="El material describe el proceso completo.",
        rubric="2: nombra alimento y luz. 1: solo uno. 0: ninguno.",
        provenance=PROVENANCE,
    )


def verdict(accepted: bool, item_id: str = "it-1") -> ItemVerdict:
    return ItemVerdict(item_id=ItemId(item_id), accepted=accepted)


class BrokenModel:
    def structured_output(self, output_model, prompt, system_prompt=None):
        async def failing():
            raise RuntimeError("boom")
            yield {}

        return failing()


async def test_critic_maps_known_flaws_and_drops_unknown_ones():
    model = LocalPlaybackModel(
        [
            {
                "accepted": False,
                "flaws": ["ambiguous", "sounds_weird", "Ungradable", "ambiguous"],
                "notes": "two options defensible",
            }
        ]
    )

    result = await critique(mcq(), SOURCE, 4, model)

    assert result.accepted is False
    assert result.flaws == [ItemFlaw.AMBIGUOUS, ItemFlaw.UNGRADABLE]
    assert result.notes == "two options defensible"
    assert result.item_id == "it-1"


async def test_critic_accepts_a_clean_item_and_sends_grade_and_source():
    model = LocalPlaybackModel([{"accepted": True, "flaws": [], "notes": "grounded in the text"}])

    result = await critique(mcq(), SOURCE, 4, model)

    assert result.accepted is True
    assert result.flaws == []
    assert "grade 4" in model.calls[0]["system_prompt"]


async def test_critic_fails_closed_when_the_model_breaks():
    result = await critique(mcq(), SOURCE, 4, BrokenModel())

    assert result.accepted is False
    assert result.flaws == [ItemFlaw.UNGRADABLE]
    assert result.notes == CRITIC_ERROR_NOTE


async def test_probe_detects_a_giveaway_item_answered_from_general_knowledge():
    model = LocalPlaybackModel([{"answer": "  la FOTOSÍNTESIS "}])

    assert await probe_blind(mcq(), model) is True


async def test_probe_accepts_a_one_based_option_number_as_the_answer():
    model = LocalPlaybackModel([{"answer": "2."}])

    assert await probe_blind(mcq(), model) is True


async def test_probe_returns_false_when_the_blind_student_guesses_wrong():
    model = LocalPlaybackModel([{"answer": "La digestión"}])

    assert await probe_blind(mcq(), model) is False


def test_the_blind_prompt_shows_only_the_stem_and_the_options():
    rendered = render_blind(mcq())

    assert "La fotosíntesis" in rendered
    assert SOURCE not in rendered
    assert "Answer key" not in rendered
    assert "rationale" not in rendered.casefold()


async def test_probe_returns_none_for_open_items_without_calling_the_model():
    model = LocalPlaybackModel([{"answer": "no debería usarse"}])

    assert await probe_blind(open_item(), model) is None
    assert model.calls == []


async def test_probe_returns_none_when_the_model_breaks():
    assert await probe_blind(mcq(), BrokenModel()) is None


def test_combine_flips_acceptance_and_appends_the_flaw():
    result = combine(verdict(accepted=True), True)

    assert result.accepted is False
    assert result.flaws == [ItemFlaw.ANSWERABLE_WITHOUT_MATERIAL]
    assert result.probe_answered_blind is True


def test_combine_never_duplicates_a_flaw_the_critic_already_found():
    critic = ItemVerdict(
        item_id=ItemId("it-1"),
        accepted=False,
        flaws=[ItemFlaw.ANSWERABLE_WITHOUT_MATERIAL],
    )

    assert combine(critic, True).flaws == [ItemFlaw.ANSWERABLE_WITHOUT_MATERIAL]


def test_combine_keeps_acceptance_when_the_probe_failed_or_missed():
    for answered_blind in (False, None):
        result = combine(verdict(accepted=True), answered_blind)
        assert result.accepted is True
        assert result.flaws == []
        assert result.probe_answered_blind is answered_blind


def test_combine_keeps_a_rejection_the_critic_already_made():
    result = combine(verdict(accepted=False), False)

    assert result.accepted is False
    assert result.probe_answered_blind is False


def test_rejection_rate_counts_the_proportion_rejected():
    verdicts = [verdict(True), verdict(False), verdict(True), verdict(False)]

    assert rejection_rate(verdicts) == 0.5
    assert rejection_rate([verdict(False)]) == 1.0
    assert rejection_rate([verdict(True)]) == 0.0


def test_rejection_rate_of_an_empty_list_is_zero():
    assert rejection_rate([]) == 0.0
