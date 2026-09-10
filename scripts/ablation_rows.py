"""One capture row per item, permutation and arm, in the pre-registered column order."""

import csv
from pathlib import Path

from ablation_arms import ADVISORY_PROBE, CRITIC_ONLY, FORCED_CHOICE_VETO, PROMPT_VERSIONS
from ablation_arms import arm_verdicts as verdicts_for
from ablation_items import FrozenItem, key_planted_wrong
from ablation_run import STAGE_ADVISORY, STAGE_CRITIC, STAGE_FORCED_CHOICE, CallLog, Review

from repaso.schemas.common import FrozenStrictModel, ItemId
from repaso.schemas.item import ItemFlaw, ItemVerdict

NO_REVIEWER = "none"
ARM_STAGES = {
    CRITIC_ONLY: (STAGE_CRITIC,),
    FORCED_CHOICE_VETO: (STAGE_CRITIC, STAGE_FORCED_CHOICE),
    ADVISORY_PROBE: (STAGE_CRITIC, STAGE_ADVISORY),
}
COLUMNS = (
    "item_id",
    "source_page",
    "independent_reviewer",
    "label_source",
    "construction_valid",
    "construction_option_clue",
    "arm",
    "permutation_seed",
    "model_id",
    "prompt_version",
    "critic_valid",
    "probe_choice",
    "accepted",
    "key_correct",
    "input_tokens",
    "output_tokens",
    "latency_ms",
    "error",
)
BOOL_COLUMNS = frozenset(
    ("construction_valid", "construction_option_clue", "critic_valid", "accepted", "key_correct")
)


class Observation(FrozenStrictModel):
    item_id: str
    source_page: str
    independent_reviewer: str
    label_source: str
    construction_valid: bool
    construction_option_clue: bool
    arm: str
    permutation_seed: int
    model_id: str
    prompt_version: str
    critic_valid: bool
    probe_choice: str
    accepted: bool
    key_correct: bool
    input_tokens: int
    output_tokens: int
    latency_ms: float
    error: str


def _critic_verdict(review: Review) -> ItemVerdict:
    return ItemVerdict(
        item_id=ItemId(review.item_id),
        accepted=review.critic_accepted,
        flaws=[ItemFlaw(flaw) for flaw in review.critic_flaws],
        notes=review.critic_notes,
    )


def _stage_calls(review: Review, arm: str) -> list[CallLog]:
    return [call for call in review.calls if call.stage in ARM_STAGES[arm]]


def _probe_reply(review: Review, arm: str):
    if arm == FORCED_CHOICE_VETO:
        return review.forced_choice
    if arm == ADVISORY_PROBE:
        return review.advisory
    return None


def observations(review: Review, item: FrozenItem, label_source: str) -> list[Observation]:
    verdicts = verdicts_for(_critic_verdict(review), review.forced_choice, review.advisory)
    rows = []
    for arm in ARM_STAGES:
        calls = _stage_calls(review, arm)
        reply = _probe_reply(review, arm)
        errors = [call.error for call in calls if call.error]
        if reply is not None and reply.error:
            errors.append(reply.error)
        rows.append(
            Observation(
                item_id=item.item_id,
                source_page=item.source_page,
                independent_reviewer=NO_REVIEWER,
                label_source=label_source,
                construction_valid=item.construction_valid,
                construction_option_clue=item.construction_option_clue,
                arm=arm,
                permutation_seed=review.permutation_seed,
                model_id="+".join(dict.fromkeys(call.model_id for call in calls)),
                prompt_version=PROMPT_VERSIONS[arm],
                critic_valid=review.critic_accepted,
                probe_choice="" if reply is None else reply.answer,
                accepted=verdicts[arm].accepted,
                key_correct=not key_planted_wrong(item),
                input_tokens=sum(call.input_tokens for call in calls),
                output_tokens=sum(call.output_tokens for call in calls),
                latency_ms=round(sum(call.latency_ms for call in calls), 1),
                error="; ".join(errors),
            )
        )
    return rows


def _cell(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def write_rows(path: Path, rows: list[Observation]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        for row in rows:
            dumped = row.model_dump()
            writer.writerow([_cell(dumped[column]) for column in COLUMNS])


def read_rows(path: Path) -> list[Observation]:
    with path.open(encoding="utf-8", newline="") as handle:
        raw = list(csv.DictReader(handle))
    return [
        Observation.model_validate(
            {key: value == "true" if key in BOOL_COLUMNS else value for key, value in row.items()}
        )
        for row in raw
    ]
