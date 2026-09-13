from repaso.core.orchestration.context import Services
from repaso.i18n.competencies import competency_label
from repaso.schemas.common import Lang
from repaso.schemas.competency import Competency
from repaso.tools.lexical_ranking import coverage, token_weights, tokenize

SUBJECT = "math"
MATCH_FLOOR = 0.5
WEIGHT_FLOOR = 0.5
MIN_TOKEN_LENGTH = 4


def _document(competency: Competency, lang: Lang) -> str:
    return " ".join(
        (
            competency_label(competency, lang),
            competency.name,
            competency.description,
            str(competency.id).replace(".", " ").replace("_", " "),
        )
    )


def _asked_for(topic: str, weights: dict[str, float]) -> set[str]:
    return {
        token
        for token in tokenize(topic)
        if len(token) >= MIN_TOKEN_LENGTH and weights.get(token, 0.0) >= WEIGHT_FLOOR
    }


def _match(asked: set[str], document: set[str], weights: dict[str, float]) -> float:
    mass = sum(weights[token] for token in asked)
    shared = sum(weights[token] for token in asked & document)
    return shared / mass


def resolve_topic(services: Services, grade: int, topic: str, lang: Lang) -> Competency | None:
    competencies = services.retriever.list_competencies(grade, SUBJECT)
    documents = {str(c.id): tokenize(_document(c, lang)) for c in competencies}
    if not documents:
        return None
    weights = token_weights(list(documents.values()))
    asked = _asked_for(topic, weights)
    if not asked:
        return None
    scored = sorted(
        (
            (_match(asked, tokens, weights), coverage(asked, tokens, weights), key)
            for key, tokens in documents.items()
        ),
        key=lambda row: (-row[0], -row[1], row[2]),
    )
    score, _, best = scored[0]
    if score < MATCH_FLOOR:
        return None
    return next(c for c in competencies if str(c.id) == best)
