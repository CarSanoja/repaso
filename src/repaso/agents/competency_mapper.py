from typing import Annotated

from pydantic import BaseModel

from repaso.agents.base import StructuredCallFailed, structured
from repaso.agents.prompts.competency_mapper import PROMPT_VERSION, SYSTEM
from repaso.schemas.common import CompetencyId
from repaso.schemas.competency import (
    Competency,
    CompetencyMatch,
    MappingOutcome,
    MaterialMapping,
)
from repaso.schemas.nullable import NULL_IS_EMPTY
from repaso.tools.knowledge import KnowledgeRetriever

CANDIDATE_LIMIT = 24


class MappingDecision(BaseModel):
    competency_ids: Annotated[list[str], NULL_IS_EMPTY] = []


def _describe(competency: Competency) -> str:
    return f"{competency.id}: {competency.name} — {competency.description}"


def ordered_candidates(
    hints: list[CompetencyMatch], slate: list[Competency]
) -> list[Competency]:
    by_id = {str(competency.id): competency for competency in slate}
    ordered: list[Competency] = []
    seen: set[str] = set()
    for hint in hints:
        key = str(hint.competency_id)
        if key in by_id and key not in seen:
            seen.add(key)
            ordered.append(by_id[key])
    ordered.extend(competency for competency in slate if str(competency.id) not in seen)
    return ordered[:CANDIDATE_LIMIT]


def request_text(parsed_text: str, candidates: list[Competency], limit: int) -> str:
    lines = "\n".join(_describe(competency) for competency in candidates)
    return (
        f"Curriculum:\n{lines}\n\n"
        f"Pick at most {limit} ids from that list, most relevant first.\n\n"
        f"Page:\n{parsed_text}"
    )


def _keep_known(
    chosen: list[str], candidates: list[Competency], limit: int
) -> list[CompetencyId]:
    known = {str(competency.id) for competency in candidates}
    kept: list[CompetencyId] = []
    for competency_id in chosen:
        key = str(competency_id)
        if key not in known or CompetencyId(key) in kept:
            continue
        kept.append(CompetencyId(key))
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
) -> MaterialMapping:
    if limit < 1:
        raise ValueError("limit must be positive")
    slate = retriever.list_competencies(grade, subject)
    hints = retriever.retrieve(parsed_text, grade, subject, limit=CANDIDATE_LIMIT)
    candidates = ordered_candidates(hints, slate)
    if not candidates:
        return MaterialMapping(outcome=MappingOutcome.UNMATCHED)
    system = SYSTEM.format(grade=grade, subject=subject, limit=limit)
    try:
        decision = await structured(
            model,
            MappingDecision,
            system,
            request_text(parsed_text, candidates, limit),
            PROMPT_VERSION,
        )
    except StructuredCallFailed:
        return MaterialMapping(outcome=MappingOutcome.UNDETERMINED)
    kept = _keep_known(decision.competency_ids, candidates, limit)
    outcome = MappingOutcome.MAPPED if kept else MappingOutcome.UNMATCHED
    return MaterialMapping(outcome=outcome, competency_ids=kept)
