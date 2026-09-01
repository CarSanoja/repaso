from collections.abc import Mapping

from pydantic import Field

from repaso.schemas.common import FrozenStrictModel

ENABLE_KEY = "REPASO_LIVE_TESTS"
REGION_KEYS = ("REPASO_AWS_REGION", "AWS_REGION")
SAMPLES_KEY = "REPASO_LIVE_SAMPLES"
BUDGET_KEY = "REPASO_LIVE_BUDGET_USD"

DEFAULT_SAMPLES = 5
DEFAULT_BUDGET_USD = 2.00

DISABLED_REASON = f"{ENABLE_KEY}=1 is not set"
NO_REGION_REASON = f"neither {' nor '.join(REGION_KEYS)} names an AWS region"


class LiveEnvironmentInvalid(ValueError):
    pass


class LiveEnvironment(FrozenStrictModel):
    enabled: bool
    region: str | None
    samples: int = Field(ge=1)
    budget_usd: float = Field(gt=0.0)


def _region(env: Mapping[str, str]) -> str | None:
    for key in REGION_KEYS:
        value = (env.get(key) or "").strip()
        if value:
            return value
    return None


def _number[T: (int, float)](env: Mapping[str, str], key: str, default: T, parse: type[T]) -> T:
    raw = (env.get(key) or "").strip()
    if not raw:
        return default
    try:
        return parse(raw)
    except ValueError as error:
        raise LiveEnvironmentInvalid(f"{key} must be a number, got {raw!r}") from error


def read_environment(env: Mapping[str, str]) -> LiveEnvironment:
    samples = _number(env, SAMPLES_KEY, DEFAULT_SAMPLES, int)
    budget = _number(env, BUDGET_KEY, DEFAULT_BUDGET_USD, float)
    if samples < 1:
        raise LiveEnvironmentInvalid(f"{SAMPLES_KEY} must be at least 1, got {samples}")
    if budget <= 0:
        raise LiveEnvironmentInvalid(f"{BUDGET_KEY} must be above zero, got {budget}")
    return LiveEnvironment(
        enabled=(env.get(ENABLE_KEY) or "").strip() == "1",
        region=_region(env),
        samples=samples,
        budget_usd=budget,
    )


def skip_reason(environment: LiveEnvironment) -> str | None:
    if not environment.enabled:
        return DISABLED_REASON
    if environment.region is None:
        return NO_REGION_REASON
    return None
