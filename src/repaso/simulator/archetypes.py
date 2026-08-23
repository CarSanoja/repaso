from enum import StrEnum

from pydantic import Field

from repaso.schemas.common import FrozenStrictModel


class Archetype(StrEnum):
    STEADY_MASTERY = "steady_mastery"
    STRUGGLING = "struggling"
    DISENGAGED = "disengaged"
    FAST_GUESSER = "fast_guesser"
    COHORT_CLUSTER = "cohort_cluster"
    FORGETTING = "forgetting"
    AMBIGUOUS = "ambiguous"
    INJECTOR = "injector"


class ArchetypeProfile(FrozenStrictModel):
    archetype: Archetype
    base_ability: float = Field(ge=0.0, le=1.0)
    learning_rate: float = Field(ge=0.0, le=0.5)
    forgetting_rate: float = Field(ge=0.0, le=0.5)
    response_rate: float = Field(ge=0.0, le=1.0)
    dropout_day: int | None = None
    latency_mean: float = Field(gt=0.0)
    guess_probability: float = Field(ge=0.0, le=1.0)


PROFILES: dict[Archetype, ArchetypeProfile] = {
    Archetype.STEADY_MASTERY: ArchetypeProfile(
        archetype=Archetype.STEADY_MASTERY, base_ability=0.6, learning_rate=0.08,
        forgetting_rate=0.02, response_rate=0.95, latency_mean=35.0, guess_probability=0.0,
    ),
    Archetype.STRUGGLING: ArchetypeProfile(
        archetype=Archetype.STRUGGLING, base_ability=0.2, learning_rate=0.02,
        forgetting_rate=0.1, response_rate=0.9, latency_mean=70.0, guess_probability=0.1,
    ),
    Archetype.DISENGAGED: ArchetypeProfile(
        archetype=Archetype.DISENGAGED, base_ability=0.55, learning_rate=0.05,
        forgetting_rate=0.05, response_rate=1.0, dropout_day=6, latency_mean=40.0,
        guess_probability=0.05,
    ),
    Archetype.FAST_GUESSER: ArchetypeProfile(
        archetype=Archetype.FAST_GUESSER, base_ability=0.75, learning_rate=0.03,
        forgetting_rate=0.03, response_rate=0.95, latency_mean=4.0, guess_probability=0.5,
    ),
    Archetype.COHORT_CLUSTER: ArchetypeProfile(
        archetype=Archetype.COHORT_CLUSTER, base_ability=0.25, learning_rate=0.02,
        forgetting_rate=0.12, response_rate=0.9, latency_mean=60.0, guess_probability=0.1,
    ),
    Archetype.FORGETTING: ArchetypeProfile(
        archetype=Archetype.FORGETTING, base_ability=0.7, learning_rate=0.06,
        forgetting_rate=0.25, response_rate=0.95, latency_mean=45.0, guess_probability=0.0,
    ),
    Archetype.AMBIGUOUS: ArchetypeProfile(
        archetype=Archetype.AMBIGUOUS, base_ability=0.5, learning_rate=0.05,
        forgetting_rate=0.05, response_rate=0.95, latency_mean=55.0, guess_probability=0.0,
    ),
    Archetype.INJECTOR: ArchetypeProfile(
        archetype=Archetype.INJECTOR, base_ability=0.5, learning_rate=0.05,
        forgetting_rate=0.05, response_rate=0.95, latency_mean=30.0, guess_probability=0.0,
    ),
}

MISCONCEPTIONS: dict[str, str] = {
    "math.g4.fractions.equivalence": "2/4 y 3/4 son equivalentes porque terminan igual",
    "math.g4.fractions.addition_same_denominator": "1/4 + 2/4 = 3/8",
    "math.g4.place_value.to_10000": "en 3407 el 4 vale 4",
    "math.g4.division.with_remainder": "17 entre 5 da 3 y sobra 0",
    "math.g4.measurement.length_conversion": "1 metro con 20 cm son 1.2 cm",
    "math.g4.decimals.tenths_hundredths": "0.5 es menor que 0.45 porque 5 es menor que 45",
}

DEFAULT_WRONG_ANSWER = "no estoy seguro, creo que es otra"
