import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from ablation_items import NO_DEFECT, plant  # noqa: E402
from ablation_run import (  # noqa: E402
    STAGE_ADVISORY,
    STAGE_CRITIC,
    STAGE_CRITIC_REPEAT,
    STAGE_FORCED_CHOICE,
    CapturingLedger,
    review_item,
)

from repaso.core.telemetry.sink import NullTelemetrySink  # noqa: E402
from repaso.schemas.common import CompetencyId, ItemId  # noqa: E402
from repaso.schemas.item import Item, ItemKind  # noqa: E402
from repaso.schemas.provenance import Provenance, Source  # noqa: E402
from repaso.tools.call_ledger import NullCallLedger  # noqa: E402
from repaso.tools.instrumented_model import InstrumentedModel  # noqa: E402
from repaso.tools.llm import LocalPlaybackModel  # noqa: E402

NOW = datetime(2026, 9, 12, tzinfo=UTC)
SOURCE = "Regla del cuaderno: multiplico arriba y abajo por el mismo número."


def generated() -> Item:
    return Item(
        id=ItemId("it-1"),
        competency_id=CompetencyId("math.g4.fractions.equivalence"),
        kind=ItemKind.MCQ,
        difficulty=2,
        stem="¿Cuál fracción es equivalente a 1/2?",
        options=["2/4", "1/6", "3/4"],
        answer_key="2/4",
        rationale="Multiplico arriba y abajo por dos.",
        provenance=Provenance(source=Source.GENERATED, created_at=NOW),
    )


def instrumented(role: str, script: list[dict], ledger: CapturingLedger) -> InstrumentedModel:
    return InstrumentedModel(
        LocalPlaybackModel(script), role, NullTelemetrySink(), ledger=ledger
    )


async def run(script_judge: list[dict], script_probe: list[dict], repeat: bool = False):
    ledger = CapturingLedger(NullCallLedger())
    frozen = plant(generated(), NO_DEFECT, "demo/cuaderno-fracciones.png")
    review = await review_item(
        frozen,
        1,
        SOURCE,
        4,
        instrumented("judge", script_judge, ledger),
        instrumented("probe", script_probe, ledger),
        ledger,
        NOW,
        "model-under-test",
        repeat_critic=repeat,
    )
    return review, ledger


async def test_one_review_makes_one_critic_call_and_one_call_per_probe():
    review, ledger = await run(
        [{"accepted": True, "flaws": [], "notes": "survived"}],
        [{"answer": "2/4"}, {"answer": "UNKNOWN"}],
    )
    assert [call.stage for call in review.calls] == [
        STAGE_CRITIC,
        STAGE_FORCED_CHOICE,
        STAGE_ADVISORY,
    ]
    assert len(ledger.written) == 3
    assert review.critic_accepted
    assert review.forced_choice.matched_key is True
    assert review.advisory.matched_key is False


async def test_the_repeat_critic_pass_is_a_fourth_call_that_no_arm_reads():
    review, _ = await run(
        [
            {"accepted": True, "flaws": [], "notes": "survived"},
            {"accepted": False, "flaws": ["ambiguous"], "notes": "two defensible options"},
        ],
        [{"answer": "2/4"}, {"answer": "UNKNOWN"}],
        repeat=True,
    )
    assert [call.stage for call in review.calls][:2] == [STAGE_CRITIC, STAGE_CRITIC_REPEAT]
    assert review.critic_accepted is True
    assert review.critic_repeat_accepted is False


async def test_every_call_the_review_made_is_attributed_to_exactly_one_stage():
    review, ledger = await run(
        [{"accepted": False, "flaws": ["implausible_distractors"], "notes": "no student"}],
        [{"answer": "1"}, {"answer": "1"}],
    )
    written = [record.call_id for record in ledger.written]
    assert [call.call_id for call in review.calls] == written
    assert len(set(written)) == len(written)
    assert review.critic_flaws == ["implausible_distractors"]
