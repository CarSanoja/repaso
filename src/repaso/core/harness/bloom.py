from repaso.schemas.item import BloomLevel

BLOOM_ORDER: tuple[BloomLevel, ...] = (
    BloomLevel.REMEMBER,
    BloomLevel.UNDERSTAND,
    BloomLevel.APPLY,
    BloomLevel.ANALYZE,
)

ALIASES: dict[str, BloomLevel] = {
    "remember": BloomLevel.REMEMBER,
    "recall": BloomLevel.REMEMBER,
    "recordar": BloomLevel.REMEMBER,
    "understand": BloomLevel.UNDERSTAND,
    "understanding": BloomLevel.UNDERSTAND,
    "comprender": BloomLevel.UNDERSTAND,
    "entender": BloomLevel.UNDERSTAND,
    "apply": BloomLevel.APPLY,
    "application": BloomLevel.APPLY,
    "aplicar": BloomLevel.APPLY,
    "analyze": BloomLevel.ANALYZE,
    "analyse": BloomLevel.ANALYZE,
    "analizar": BloomLevel.ANALYZE,
}


def parse_bloom(value: str | None) -> BloomLevel | None:
    if not value:
        return None
    word = value.strip().strip(".:;,").casefold()
    return ALIASES.get(word)


def bloom_distance(left: BloomLevel, right: BloomLevel) -> int:
    return abs(BLOOM_ORDER.index(left) - BLOOM_ORDER.index(right))


def nearest_levels(level: BloomLevel) -> tuple[BloomLevel, ...]:
    return tuple(sorted(BLOOM_ORDER, key=lambda other: (bloom_distance(level, other), other.value)))
