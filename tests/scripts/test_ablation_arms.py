import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from ablation_arms import (  # noqa: E402
    ADVISORY_PROBE,
    CRITIC_ONLY,
    FORCED_CHOICE_VETO,
    ProbeReply,
    arm_verdicts,
    ask_advisory,
    ask_forced_choice,
    render_forced_choice,
)

from repaso.schemas.common import CompetencyId, ItemId  # noqa: E402
from repaso.schemas.item import Item, ItemFlaw, ItemKind, ItemVerdict  # noqa: E402
from repaso.schemas.provenance import Provenance, Source  # noqa: E402
from repaso.tools.llm import LocalPlaybackModel  # noqa: E402

NOW = datetime(2026, 9, 12, tzinfo=UTC)
OPTIONS = ["2/4", "1/6", "3/4"]


def mcq() -> Item:
    return Item(
        id=ItemId("it-1"),
        competency_id=CompetencyId("math.g4.fractions.equivalence"),
        kind=ItemKind.MCQ,
        difficulty=2,
        stem="¿Cuál fracción es equivalente a 1/2?",
        options=OPTIONS,
        answer_key="2/4",
        rationale="Multiplico arriba y abajo por dos.",
        provenance=Provenance(source=Source.GENERATED, created_at=NOW),
    )


class RefusingModel:
    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        raise RuntimeError("provider refused the call")
        yield {}


def accepted() -> ItemVerdict:
    return ItemVerdict(item_id=ItemId("it-1"), accepted=True, notes="survived")


async def test_the_forced_choice_probe_is_shown_the_stem_and_scores_its_pick():
    model = LocalPlaybackModel([{"answer": "2/4"}])
    reply = await ask_forced_choice(mcq(), model)
    assert reply.matched_key is True
    assert "¿Cuál fracción es equivalente a 1/2?" in render_forced_choice(mcq())


async def test_the_advisory_probe_never_sees_the_stem():
    model = LocalPlaybackModel([{"answer": "1"}])
    reply = await ask_advisory(mcq(), model)
    assert reply.matched_key is True
    assert model.calls[0]["kind"] == "structured_output"


async def test_an_option_number_counts_as_naming_that_option():
    model = LocalPlaybackModel([{"answer": "3"}])
    assert (await ask_forced_choice(mcq(), model)).matched_key is False


async def test_a_probe_that_declines_to_choose_has_not_matched_the_key():
    model = LocalPlaybackModel([{"answer": "UNKNOWN"}])
    reply = await ask_advisory(mcq(), model)
    assert reply.matched_key is False
    assert reply.answer == "UNKNOWN"


async def test_a_probe_call_that_fails_is_kept_as_an_error_and_not_as_a_choice():
    reply = await ask_forced_choice(mcq(), RefusingModel())
    assert reply.matched_key is None
    assert "provider refused" in reply.error


def test_the_historical_arm_discards_an_item_the_probe_answered():
    hit = ProbeReply(answer="2/4", matched_key=True)
    verdicts = arm_verdicts(accepted(), hit, ProbeReply(answer="UNKNOWN", matched_key=False))
    assert verdicts[CRITIC_ONLY].accepted
    assert not verdicts[FORCED_CHOICE_VETO].accepted
    assert ItemFlaw.ANSWERABLE_WITHOUT_MATERIAL in verdicts[FORCED_CHOICE_VETO].flaws


def test_the_advisory_arm_records_the_same_hit_and_keeps_the_item():
    hit = ProbeReply(answer="2/4", matched_key=True)
    verdicts = arm_verdicts(accepted(), hit, hit)
    assert verdicts[ADVISORY_PROBE].accepted
    assert verdicts[ADVISORY_PROBE].probe_answered_blind is True
    assert verdicts[ADVISORY_PROBE].flaws == []


def test_no_arm_revives_an_item_the_critic_rejected():
    rejected = ItemVerdict(item_id=ItemId("it-1"), accepted=False, flaws=[ItemFlaw.AMBIGUOUS])
    miss = ProbeReply(answer="1/6", matched_key=False)
    verdicts = arm_verdicts(rejected, miss, miss)
    assert not any(verdict.accepted for verdict in verdicts.values())
