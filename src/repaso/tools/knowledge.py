import json
import re
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from repaso.config.settings import Settings
from repaso.schemas.common import CompetencyId
from repaso.schemas.competency import Competency, CompetencyMatch

FIXTURES_DIR = Path(__file__).parent / "fixtures"
DEFAULT_TAXONOMY_PATH = FIXTURES_DIR / "curriculum_math_primary.json"
DEFAULT_LIMIT = 5
MAX_LIST_RESULTS = 100
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
STOPWORDS = frozenset(
    (
        "a an and are as at be by can for from how in into is it of on or "
        "that the them this to what which with"
    ).split()
)


@runtime_checkable
class KnowledgeRetriever(Protocol):
    def retrieve(
        self, query: str, grade: int, subject: str, limit: int = DEFAULT_LIMIT
    ) -> list[CompetencyMatch]: ...

    def get_competency(self, competency_id: CompetencyId) -> Competency | None: ...

    def list_competencies(self, grade: int, subject: str) -> list[Competency]: ...


def tokenize(text: str) -> set[str]:
    return {token for token in TOKEN_PATTERN.findall(text.lower()) if token not in STOPWORDS}


def overlap_score(query_tokens: set[str], competency: Competency) -> float:
    if not query_tokens:
        return 0.0
    target = tokenize(f"{competency.name} {competency.description}")
    return len(query_tokens & target) / len(query_tokens)


class LocalTaxonomyRetriever:
    def __init__(self, taxonomy_path: Path | str | None = None) -> None:
        self.taxonomy_path = Path(taxonomy_path) if taxonomy_path else DEFAULT_TAXONOMY_PATH
        self._by_id: dict[str, Competency] | None = None

    def _load(self) -> dict[str, Competency]:
        if self._by_id is None:
            raw = json.loads(self.taxonomy_path.read_text(encoding="utf-8"))
            entries = raw["competencies"] if isinstance(raw, dict) else raw
            self._by_id = {str(entry["id"]): Competency(**entry) for entry in entries}
        return self._by_id

    def retrieve(
        self, query: str, grade: int, subject: str, limit: int = DEFAULT_LIMIT
    ) -> list[CompetencyMatch]:
        if limit < 1:
            raise ValueError("limit must be positive")
        tokens = tokenize(query)
        scored = [
            (overlap_score(tokens, competency), str(competency.id))
            for competency in self.list_competencies(grade, subject)
        ]
        ranked = sorted(
            ((score, key) for score, key in scored if score > 0.0),
            key=lambda pair: (-pair[0], pair[1]),
        )
        return [
            CompetencyMatch(competency_id=CompetencyId(key), confidence=round(score, 6))
            for score, key in ranked[:limit]
        ]

    def get_competency(self, competency_id: CompetencyId) -> Competency | None:
        return self._load().get(str(competency_id))

    def list_competencies(self, grade: int, subject: str) -> list[Competency]:
        return sorted(
            (
                competency
                for competency in self._load().values()
                if competency.grade == grade and competency.subject == subject
            ),
            key=lambda competency: competency.id,
        )


def _grade_subject_filters(grade: int, subject: str) -> dict[str, Any]:
    return {
        "andAll": [
            {"equals": {"key": "grade", "value": grade}},
            {"equals": {"key": "subject", "value": subject}},
        ]
    }


def _competency_from_metadata(metadata: dict[str, Any]) -> Competency | None:
    fields = ("competency_id", "subject", "grade", "name", "description")
    if any(field not in metadata for field in fields):
        return None
    return Competency(
        id=CompetencyId(str(metadata["competency_id"])),
        subject=str(metadata["subject"]),
        grade=int(metadata["grade"]),
        name=str(metadata["name"]),
        description=str(metadata["description"]),
    )


class KnowledgeBaseRetriever:
    def __init__(self, knowledge_base_id: str, region_name: str | None = None) -> None:
        self.knowledge_base_id = knowledge_base_id
        self.region_name = region_name

    def _client(self) -> Any:
        import boto3

        return boto3.client("bedrock-agent-runtime", region_name=self.region_name)

    def _search(self, query: str, filters: dict[str, Any], limit: int) -> list[dict[str, Any]]:
        response = self._client().retrieve(
            knowledgeBaseId=self.knowledge_base_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {"numberOfResults": limit, "filter": filters}
            },
        )
        return list(response.get("retrievalResults", []))

    def retrieve(
        self, query: str, grade: int, subject: str, limit: int = DEFAULT_LIMIT
    ) -> list[CompetencyMatch]:
        if limit < 1:
            raise ValueError("limit must be positive")
        results = self._search(query, _grade_subject_filters(grade, subject), limit)
        matches = [
            CompetencyMatch(
                competency_id=CompetencyId(str(result["metadata"]["competency_id"])),
                confidence=min(1.0, max(0.0, float(result.get("score", 0.0)))),
            )
            for result in results
            if "competency_id" in result.get("metadata", {})
        ]
        return matches[:limit]

    def get_competency(self, competency_id: CompetencyId) -> Competency | None:
        key = str(competency_id)
        results = self._search(key, {"equals": {"key": "competency_id", "value": key}}, 1)
        for result in results:
            return _competency_from_metadata(result.get("metadata", {}))
        return None

    def list_competencies(self, grade: int, subject: str) -> list[Competency]:
        results = self._search(subject, _grade_subject_filters(grade, subject), MAX_LIST_RESULTS)
        found = [_competency_from_metadata(result.get("metadata", {})) for result in results]
        return sorted(
            (competency for competency in found if competency is not None),
            key=lambda competency: competency.id,
        )


def local_taxonomy_path(settings: Settings) -> Path:
    path = settings.local_data_dir / "curriculum" / DEFAULT_TAXONOMY_PATH.name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DEFAULT_TAXONOMY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def build_knowledge_retriever(
    settings: Settings, knowledge_base_id: str | None = None
) -> KnowledgeRetriever:
    if settings.local_mode:
        return LocalTaxonomyRetriever(local_taxonomy_path(settings))
    if not knowledge_base_id:
        raise ValueError("knowledge_base_id is required outside local mode")
    return KnowledgeBaseRetriever(knowledge_base_id, region_name=settings.aws_region)
