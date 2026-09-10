from typing import Annotated

from pydantic import BaseModel

from repaso.agents.base import StructuredCallFailed, structured
from repaso.agents.prompts.competency_mapper import PROMPT_VERSION, SYSTEM
from repaso.schemas.competency import CompetencyMatch
from repaso.schemas.nullable import NULL_IS_EMPTY
from repaso.tools.knowledge import KnowledgeRetriever

MIN_RETRIEVAL_SCORE = 0.15
CANDIDATE_LIMIT = 8


class MappingDecision(BaseModel):
    competency_ids: Annotated[list[str], NULL_IS_EMPTY] = []


def _describe(match: CompetencyMatch, retriever: KnowledgeRetriever) -> str:
    competency = retriever.get_competency(match.competency_id)
    if competency is None:
        return str(match.competency_id)
    return f"{competency.id}: {competency.name} — {competency.description}"


def _request_text(
    parsed_text: str,
    candidates: list[CompetencyMatch],
    retriever: KnowledgeRetriever,
    limit: int,
) -> str:
    lines = "\n".join(_describe(match, retriever) for match in candidates)
    return (
        f"Candidate competencies:\n{lines}\n\n"
        f"Pick at most {limit} ids from that list, most relevant first.\n\n"
        f"Material:\n{parsed_text}"
    )


def _by_confidence(candidates: list[CompetencyMatch], limit: int) -> list[CompetencyMatch]:
    ranked = sorted(candidates, key=lambda match: (-match.confidence, str(match.competency_id)))
    return ranked[:limit]


def _keep_known(
    chosen: list[str], candidates: list[CompetencyMatch], limit: int
) -> list[CompetencyMatch]:
    known = {str(match.competency_id): match for match in candidates}
    kept: list[CompetencyMatch] = []
    seen: set[str] = set()
    for competency_id in chosen:
        match = known.get(str(competency_id))
        if match is None or str(competency_id) in seen:
            continue
        seen.add(str(competency_id))
        kept.append(match)
        if len(kept) == limit:
            break
    return kept


async def map_material(
    parsed_text: str,
    grade: int,
    subject: str,
    retriever: KnowledgeRetriever,
    model,
    limit: int = 3,
) -> list[CompetencyMatch]:
    if limit < 1:
        raise ValueError("limit must be positive")
    candidates = retriever.retrieve(parsed_text, grade, subject, limit=CANDIDATE_LIMIT)
    if not any(match.confidence >= MIN_RETRIEVAL_SCORE for match in candidates):
        return []
    system = SYSTEM.format(grade=grade, subject=subject, limit=limit)
    try:
        decision = await structured(
            model,
            MappingDecision,
            system,
            _request_text(parsed_text, candidates, retriever, limit),
            PROMPT_VERSION,
        )
    except StructuredCallFailed:
        return _by_confidence(candidates, limit)
    return _keep_known(decision.competency_ids, candidates, limit)
