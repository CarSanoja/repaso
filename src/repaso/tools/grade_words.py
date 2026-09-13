from datetime import datetime, timedelta

from repaso.core.harness.retention import ANSWER_RETENTION_DAYS
from repaso.schemas.common import FrozenStrictModel
from repaso.schemas.grading import GradeResult

WORDS_PREFIX = "WORDS#"
WORDS_FILENAME = "grade_words.jsonl"


class ChildWords(FrozenStrictModel):
    key: str
    quote: str
    expires_at: int


def stamp_of(result: GradeResult) -> str:
    return result.id or result.graded_at.isoformat()


def words_key(result: GradeResult) -> str:
    return f"{result.student_id}#{result.item_id}#{stamp_of(result)}"


def expiry_of(result: GradeResult) -> int:
    horizon = result.graded_at + timedelta(days=ANSWER_RETENTION_DAYS)
    return int(horizon.timestamp())


def _quoting(result: GradeResult, quote: str) -> GradeResult:
    said = result.evidence.model_copy(update={"quote": quote})
    return result.model_copy(update={"evidence": said})


def attempt_only(result: GradeResult) -> GradeResult:
    return _quoting(result, "")


def words_of(result: GradeResult) -> ChildWords | None:
    if not result.evidence.quote.strip():
        return None
    return ChildWords(
        key=words_key(result),
        quote=result.evidence.quote,
        expires_at=expiry_of(result),
    )


def still_said(words: list[ChildWords], now: datetime) -> dict[str, str]:
    return {row.key: row.quote for row in words if row.expires_at > now.timestamp()}


def rejoin(attempts: list[GradeResult], said: dict[str, str]) -> list[GradeResult]:
    return [
        _quoting(attempt, said[key]) if (key := words_key(attempt)) in said else attempt
        for attempt in attempts
    ]
