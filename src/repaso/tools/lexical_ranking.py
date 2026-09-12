import math
import re
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence

TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return stripped.casefold()


def tokenize(text: str) -> set[str]:
    return set(TOKEN_PATTERN.findall(fold(text)))


def token_weights(documents: Sequence[set[str]]) -> dict[str, float]:
    total = len(documents)
    counts = Counter(token for document in documents for token in document)
    return {token: math.log((total + 1) / (count + 1)) for token, count in counts.items()}


def coverage(query: set[str], document: set[str], weights: Mapping[str, float]) -> float:
    mass = sum(weights.get(token, 0.0) for token in document)
    if mass <= 0.0:
        return 0.0
    shared = sum(weights.get(token, 0.0) for token in document & query)
    return min(1.0, shared / mass)


def rank(query: str, documents: Mapping[str, str]) -> list[tuple[str, float]]:
    tokenized = {key: tokenize(text) for key, text in documents.items()}
    weights = token_weights(list(tokenized.values()))
    query_tokens = tokenize(query)
    scored = [
        (key, coverage(query_tokens, tokens, weights)) for key, tokens in tokenized.items()
    ]
    return sorted(scored, key=lambda pair: (-pair[1], pair[0]))
