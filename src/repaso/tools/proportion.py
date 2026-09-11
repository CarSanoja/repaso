import math

from pydantic import Field

from repaso.schemas.common import FrozenStrictModel

Z_95 = 1.96


class ProportionInterval(FrozenStrictModel):
    successes: int = Field(ge=0)
    total: int = Field(ge=0)
    point: float = Field(ge=0.0, le=1.0)
    low: float = Field(ge=0.0, le=1.0)
    high: float = Field(ge=0.0, le=1.0)

    def line(self) -> str:
        if self.total == 0:
            return "0/0"
        return f"{self.successes}/{self.total} [{self.low:.3f}, {self.high:.3f}]"


def wilson_interval(successes: int, total: int, z: float = Z_95) -> ProportionInterval:
    if successes < 0 or total < 0:
        raise ValueError("counts cannot be negative")
    if successes > total:
        raise ValueError("successes cannot exceed the total")
    if total == 0:
        return ProportionInterval(successes=0, total=0, point=0.0, low=0.0, high=1.0)
    point = successes / total
    denominator = 1 + z * z / total
    centre = (point + z * z / (2 * total)) / denominator
    half = z * math.sqrt(point * (1 - point) / total + z * z / (4 * total * total)) / denominator
    return ProportionInterval(
        successes=successes,
        total=total,
        point=point,
        low=max(0.0, centre - half),
        high=min(1.0, centre + half),
    )
