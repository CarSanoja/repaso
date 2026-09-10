import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from ablation_arms import ProbeReply  # noqa: E402
from ablation_items import NO_DEFECT, WRONG_KEY, FrozenItem  # noqa: E402
from ablation_run import (  # noqa: E402
    STAGE_ADVISORY,
    STAGE_CRITIC,
    STAGE_FORCED_CHOICE,
    CallLog,
    Review,
)

PAGE = "demo/cuaderno-fracciones.png"
JUDGE = "us.anthropic.claude-sonnet-4-6"
PROBE = "us.amazon.nova-micro-v1:0"
STAGE_MODELS = {STAGE_CRITIC: JUDGE, STAGE_FORCED_CHOICE: PROBE, STAGE_ADVISORY: PROBE}
STAGE_TOKENS = {STAGE_CRITIC: (900, 60), STAGE_FORCED_CHOICE: (120, 8), STAGE_ADVISORY: (90, 6)}


def frozen_item(item_id: str, defect: str = NO_DEFECT, clue: bool = False) -> FrozenItem:
    return FrozenItem(
        item_id=item_id,
        source_page=PAGE,
        competency_id="math.g4.fractions.equivalence",
        difficulty=2,
        stem="¿Cuál fracción es equivalente a 1/2?",
        options=["2/4", "1/6", "3/4"],
        answer_key="1/6" if defect == WRONG_KEY else "2/4",
        rationale="Multiplico arriba y abajo por dos.",
        defect=defect,
        construction_valid=defect == NO_DEFECT,
        construction_option_clue=clue,
        generated_options=["2/4", "1/6", "3/4"],
        generated_answer_key="2/4",
    )


def call(stage: str, number: int) -> CallLog:
    tokens = STAGE_TOKENS[stage]
    return CallLog(
        stage=stage,
        call_id=f"{stage}-{number}",
        role="judge" if stage == STAGE_CRITIC else "probe",
        model_id=STAGE_MODELS[stage],
        outcome="ok",
        input_tokens=tokens[0],
        output_tokens=tokens[1],
        latency_ms=1000.0 if stage == STAGE_CRITIC else 400.0,
        usd=0.005 if stage == STAGE_CRITIC else 0.00001,
    )


def review(
    item_id: str,
    seed: int = 1,
    critic_accepted: bool = True,
    forced_hit: bool | None = False,
    advisory_hit: bool | None = False,
    repeat: bool | None = None,
) -> Review:
    return Review(
        item_id=item_id,
        permutation_seed=seed,
        options=["2/4", "1/6", "3/4"],
        answer_key="2/4",
        critic_accepted=critic_accepted,
        critic_flaws=[] if critic_accepted else ["ambiguous"],
        critic_notes="survived" if critic_accepted else "two defensible options",
        critic_repeat_accepted=repeat,
        forced_choice=ProbeReply(answer="2/4" if forced_hit else "1/6", matched_key=forced_hit),
        advisory=ProbeReply(answer="2/4" if advisory_hit else "UNKNOWN", matched_key=advisory_hit),
        calls=[call(stage, seed) for stage in (STAGE_CRITIC, STAGE_FORCED_CHOICE, STAGE_ADVISORY)],
    )
