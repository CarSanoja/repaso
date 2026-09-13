from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

from repaso.core.harness.clock import local_date
from repaso.schemas.episode import AttemptEpisode
from repaso.schemas.mastery import MasteryState
from repaso.tools.proportion import wilson_interval

EVIDENCE_FLOOR = 0.5


class ProgressBucket(StrEnum):
    HOLDS = "holds"
    NEEDS_HELP = "needs_help"
    NOT_YET_KNOWN = "not_yet_known"


@dataclass(frozen=True)
class ProgressReadout:
    practised: int
    answers: int
    correct: int
    holds: int
    needs_help: int
    not_yet_known: int


def bucket_of(correct: int, attempts: int) -> ProgressBucket:
    interval = wilson_interval(correct, attempts)
    if interval.low > EVIDENCE_FLOOR:
        return ProgressBucket.HOLDS
    if interval.high < EVIDENCE_FLOOR:
        return ProgressBucket.NEEDS_HELP
    return ProgressBucket.NOT_YET_KNOWN


def read_progress(states: list[MasteryState]) -> ProgressReadout:
    practised = [state for state in states if state.attempts]
    buckets = Counter(bucket_of(state.correct, state.attempts) for state in practised)
    return ProgressReadout(
        practised=len(practised),
        answers=sum(state.attempts for state in practised),
        correct=sum(state.correct for state in practised),
        holds=buckets[ProgressBucket.HOLDS],
        needs_help=buckets[ProgressBucket.NEEDS_HELP],
        not_yet_known=buckets[ProgressBucket.NOT_YET_KNOWN],
    )


def practice_days(episodes: list[AttemptEpisode]) -> int:
    return len({local_date(episode.occurred_at) for episode in episodes})
