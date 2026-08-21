from statistics import fmean, pstdev

from repaso.schemas.common import FrozenStrictModel

MIN_OBSERVATIONS = 5
P_CEILING = 0.95
P_FLOOR = 0.05
DISCRIMINATION_FLOOR = 0.15


class ItemObservation(FrozenStrictModel):
    item_id: str
    student_id: str
    correct: bool
    student_total_score: float


def item_p_value(observations: list[ItemObservation]) -> float:
    if not observations:
        raise ValueError("observations must not be empty")
    return fmean(1.0 if observation.correct else 0.0 for observation in observations)


def item_discrimination(observations: list[ItemObservation]) -> float:
    if len(observations) < MIN_OBSERVATIONS:
        return 0.0
    outcomes = [1.0 if observation.correct else 0.0 for observation in observations]
    scores = [observation.student_total_score for observation in observations]
    outcome_spread = pstdev(outcomes)
    score_spread = pstdev(scores)
    if outcome_spread == 0.0 or score_spread == 0.0:
        return 0.0
    outcome_mean = fmean(outcomes)
    score_mean = fmean(scores)
    covariance = fmean(
        (outcome - outcome_mean) * (score - score_mean)
        for outcome, score in zip(outcomes, scores, strict=True)
    )
    return max(-1.0, min(1.0, covariance / (outcome_spread * score_spread)))


def should_retire(observations: list[ItemObservation], min_attempts: int) -> bool:
    if not observations or len(observations) < min_attempts:
        return False
    p_value = item_p_value(observations)
    if p_value >= P_CEILING or p_value <= P_FLOOR:
        return True
    return abs(item_discrimination(observations)) < DISCRIMINATION_FLOOR


def summarize(observations: list[ItemObservation]) -> dict[str, float | int | None]:
    return {
        "n": len(observations),
        "p_value": item_p_value(observations) if observations else None,
        "discrimination": item_discrimination(observations),
    }
