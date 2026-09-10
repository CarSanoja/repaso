"""Per-arm retention, rejection, key correctness and cost, over construction denominators."""

from math import sqrt

from ablation_arms import ARMS, CRITIC_ONLY
from ablation_items import FrozenItem
from ablation_rows import ARM_STAGES, Observation
from ablation_run import STAGE_CRITIC_REPEAT, CallLog, Review

CONFIDENCE_Z = 1.96


def wilson(successes: int, count: int) -> list[float] | None:
    if not count:
        return None
    share = successes / count
    denominator = 1 + CONFIDENCE_Z**2 / count
    center = (share + CONFIDENCE_Z**2 / (2 * count)) / denominator
    spread = CONFIDENCE_Z * sqrt(
        share * (1 - share) / count + CONFIDENCE_Z**2 / (4 * count * count)
    )
    half = spread / denominator
    return [round(max(0.0, center - half), 4), round(min(1.0, center + half), 4)]


def rate(successes: int, count: int) -> dict:
    return {
        "count": successes,
        "of": count,
        "rate": round(successes / count, 4) if count else None,
        "wilson_95": wilson(successes, count),
    }


def _usage(calls: list[CallLog]) -> dict:
    return {
        "calls": len(calls),
        "input_tokens": sum(call.input_tokens for call in calls),
        "output_tokens": sum(call.output_tokens for call in calls),
        "usd": round(sum(call.usd for call in calls), 6),
        "latency_ms_total": round(sum(call.latency_ms for call in calls), 1),
    }


def arm_calls(reviews: list[Review], arm: str) -> list[CallLog]:
    stages = ARM_STAGES[arm]
    return [call for review in reviews for call in review.calls if call.stage in stages]


def arm_metrics(rows: list[Observation], reviews: list[Review], arm: str) -> dict:
    decisions = [row for row in rows if row.arm == arm]
    unplanted = [row for row in decisions if row.construction_valid]
    planted = [row for row in decisions if not row.construction_valid]
    accepted = [row for row in decisions if row.accepted]
    usage = _usage(arm_calls(reviews, arm))
    per_decision = len(decisions) or 1
    return {
        "decisions": len(decisions),
        "unplanted_retention": rate(sum(row.accepted for row in unplanted), len(unplanted)),
        "planted_rejection": rate(sum(not row.accepted for row in planted), len(planted)),
        "finalized_key_correctness": rate(
            sum(row.key_correct for row in accepted), len(accepted)
        ),
        "accepted": len(accepted),
        "errors": sum(bool(row.error) for row in decisions),
        **usage,
        "calls_per_decision": round(usage["calls"] / per_decision, 3),
        "usd_per_decision": round(usage["usd"] / per_decision, 6),
        "latency_ms_per_decision": round(usage["latency_ms_total"] / per_decision, 1),
    }


def by_defect(rows: list[Observation], items: dict[str, FrozenItem], arm: str) -> dict:
    decisions = [row for row in rows if row.arm == arm]
    defects = sorted({item.defect for item in items.values()})
    return {
        defect: rate(
            sum(not row.accepted for row in decisions if items[row.item_id].defect == defect),
            sum(1 for row in decisions if items[row.item_id].defect == defect),
        )
        for defect in defects
    }


def probe_signal(reviews: list[Review], items: dict[str, FrozenItem], field: str) -> dict:
    replies = [(getattr(review, field), items[review.item_id]) for review in reviews]
    answered = [(reply, item) for reply, item in replies if reply.matched_key is not None]
    hits = [(reply, item) for reply, item in answered if reply.matched_key]
    clued = [(reply, item) for reply, item in answered if item.construction_option_clue]
    clean = [(reply, item) for reply, item in answered if not item.construction_option_clue]
    return {
        "replies": len(replies),
        "failed": len(replies) - len(answered),
        "hit_rate_overall": rate(len(hits), len(answered)),
        "hit_rate_on_planted_clue": rate(
            sum(reply.matched_key for reply, _ in clued), len(clued)
        ),
        "hit_rate_without_planted_clue": rate(
            sum(reply.matched_key for reply, _ in clean), len(clean)
        ),
        "share_of_hits_that_were_clued": rate(
            sum(item.construction_option_clue for _, item in hits), len(hits)
        ),
    }


def critic_repeat(reviews: list[Review]) -> dict:
    repeated = [review for review in reviews if review.critic_repeat_accepted is not None]
    agreed = sum(
        review.critic_repeat_accepted == review.critic_accepted for review in repeated
    )
    calls = [
        call for review in reviews for call in review.calls if call.stage == STAGE_CRITIC_REPEAT
    ]
    return {
        "repeated_items": len(repeated),
        "same_decision": rate(agreed, len(repeated)),
        **_usage(calls),
    }


def label_counts(items: dict[str, FrozenItem]) -> dict:
    defects: dict[str, int] = {}
    for item in items.values():
        defects[item.defect] = defects.get(item.defect, 0) + 1
    return {
        "items": len(items),
        "unplanted": sum(item.construction_valid for item in items.values()),
        "planted": sum(not item.construction_valid for item in items.values()),
        "planted_option_clue": sum(item.construction_option_clue for item in items.values()),
        "by_defect": dict(sorted(defects.items())),
    }


def build_report(
    rows: list[Observation], reviews: list[Review], frozen: list[FrozenItem]
) -> dict:
    items = {item.item_id: item for item in frozen}
    baseline = arm_metrics(rows, reviews, CRITIC_ONLY)
    arms = {}
    for arm in ARMS:
        metrics = arm_metrics(rows, reviews, arm)
        metrics["extra_calls_vs_critic_only"] = metrics["calls"] - baseline["calls"]
        metrics["extra_usd_vs_critic_only"] = round(metrics["usd"] - baseline["usd"], 6)
        metrics["rejection_by_planted_defect"] = by_defect(rows, items, arm)
        arms[arm] = metrics
    return {
        "labels": label_counts(items),
        "permutation_seeds": sorted({review.permutation_seed for review in reviews}),
        "arms": arms,
        "probe_signal": {
            "forced_choice": probe_signal(reviews, items, "forced_choice"),
            "advisory": probe_signal(reviews, items, "advisory"),
        },
        "critic_repeat": critic_repeat(reviews),
    }
