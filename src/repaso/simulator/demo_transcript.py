from dataclasses import dataclass, field

PARENT = "Carla"
CHILD = "Sofi"
BOT = "Repaso"
AS_EXPECTED = "as expected"
NOT_AS_EXPECTED = "NOT as expected"
BUTTON_OPEN = "["
BUTTON_CLOSE = "]"


@dataclass(frozen=True)
class Speech:
    speaker: str
    text: str
    buttons: tuple[str, ...] = ()


@dataclass(frozen=True)
class Reading:
    label: str
    values: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Beat:
    name: str
    expected: str
    actual: str

    @property
    def met(self) -> bool:
        return self.expected == self.actual

    @property
    def verdict(self) -> str:
        return AS_EXPECTED if self.met else NOT_AS_EXPECTED


@dataclass
class ScenarioResult:
    transcript: list[Speech | Reading] = field(default_factory=list)
    beats: list[Beat] = field(default_factory=list)
    checkpoints: list[dict] = field(default_factory=list)

    @property
    def failures(self) -> list[Beat]:
        return [beat for beat in self.beats if not beat.met]


def render_buttons(buttons: tuple[str, ...]) -> str:
    return "  ".join(f"{BUTTON_OPEN} {label} {BUTTON_CLOSE}" for label in buttons)


def render(entry: Speech | Reading) -> list[str]:
    if isinstance(entry, Reading):
        joined = " · ".join(f"{name} {value}" for name, value in entry.values)
        return [f"      ↳ {entry.label}: {joined}"]
    lines = [f"{entry.speaker}:"]
    lines.extend(f"    {line}" for line in entry.text.splitlines())
    if entry.buttons:
        lines.append(f"    {render_buttons(entry.buttons)}")
    return lines
