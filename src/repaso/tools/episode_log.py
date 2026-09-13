from repaso.schemas.common import CompetencyId, FamilyId, SessionId, StudentId
from repaso.schemas.episode import AttemptEpisode
from repaso.schemas.grading import GradeResult, StudentResponse
from repaso.schemas.operation import OperationRecord
from repaso.tools.state_store import StateStore

EPISODE_PREFIX = "episode#"


def episode_key(episode: AttemptEpisode) -> str:
    stamp = episode.occurred_at.isoformat()
    return f"{EPISODE_PREFIX}{episode.student_id}#{stamp}#{episode.item_id}"


def record_attempt(store: StateStore, family_id: FamilyId, episode: AttemptEpisode) -> None:
    store.put_record(
        OperationRecord(
            scope=family_id,
            key=episode_key(episode),
            payload=episode.model_dump(mode="json"),
        )
    )


def list_attempts(
    store: StateStore, family_id: FamilyId, student_id: StudentId
) -> list[AttemptEpisode]:
    episodes = [
        AttemptEpisode.model_validate(record.payload)
        for record in store.list_records(family_id, f"{EPISODE_PREFIX}{student_id}#")
    ]
    return sorted(episodes, key=lambda episode: (episode.occurred_at, episode.item_id))


def record_grade(
    store: StateStore,
    family_id: FamilyId,
    session_id: SessionId,
    competency_id: CompetencyId,
    grade: GradeResult,
    response: StudentResponse,
) -> AttemptEpisode:
    episode = AttemptEpisode(
        student_id=response.student_id,
        session_id=session_id,
        competency_id=competency_id,
        item_id=response.item_id,
        correct=grade.correct,
        held=grade.quarantined,
        graded_by=grade.graded_by,
        latency_seconds=response.latency_seconds,
        occurred_at=response.received_at,
    )
    record_attempt(store, family_id, episode)
    return episode
