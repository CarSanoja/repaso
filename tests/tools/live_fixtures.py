from datetime import UTC, datetime, timedelta

from repaso.config.models import model_for
from repaso.tools.llm import LocalPlaybackModel
from repaso.tools.model_usage import CallUsage, usage_metadata
from tests.live.calls import run_probe
from tests.live.registry import build_registry
from tests.live.reporter import ConformanceReporter

START = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
STEP_MS = 10

PAYLOADS: dict[str, dict] = {
    "IntakeDecision": {"safe": True, "reasons": []},
    "MappingDecision": {"competency_ids": ["MAT-4-FRAC-EQUIV"]},
    "PolicyDecision": {"action": "continue", "reason": "La precisión sostiene el ritmo."},
    "GeneratedBatch": {
        "items": [
            {
                "kind": "mcq",
                "difficulty": 2,
                "stem": "¿Cuál fracción es equivalente a 3/4?",
                "options": ["6/8", "3/8", "4/3"],
                "answer_key": "6/8",
                "rationale": "Multiplicamos ambos términos por 2.",
            },
            {
                "kind": "open",
                "difficulty": 3,
                "stem": "Escribe dos fracciones equivalentes a 1/5 y explica cómo las obtuviste.",
                "options": None,
                "answer_key": "2/10 y 3/15, multiplicando ambos términos por el mismo número.",
                "rationale": "El cuaderno multiplica numerador y denominador por el mismo número.",
                "rubric": "2 puntos con explicación, 1 punto sin ella, 0 si las fracciones fallan.",
            },
        ]
    },
    "Snippet": {"text": "Dos fracciones son equivalentes cuando nombran la misma cantidad."},
    "TeacherNote": {"text": "La familia observa dificultad sostenida con fracciones."},
    "CriticFinding": {"accepted": True, "flaws": [], "notes": "The distractors are plausible."},
    "OpenGrade": {
        "correct": True,
        "rubric_points": 2.0,
        "confidence": 0.93,
        "feedback": "Muy bien explicado.",
    },
    "ProbeAnswer": {"answer": "6/8"},
    "TurnDecision": {
        "intent": "explanation",
        "speaker": "child",
        "asked_for": "Pide que le expliquen la equivalencia otra vez.",
        "answer_text": "",
    },
}


class RampClock:
    def __init__(self, start: datetime = START) -> None:
        self._now = start
        self._step_ms = STEP_MS

    def now(self) -> datetime:
        value = self._now
        self._now = self._now + timedelta(milliseconds=self._step_ms)
        self._step_ms += STEP_MS
        return value

    def today(self):
        return self._now.date()


class MeteredPlaybackModel(LocalPlaybackModel):
    def __init__(self, script, input_tokens: int, output_tokens: int) -> None:
        super().__init__(script)
        self.usage = CallUsage(input_tokens=input_tokens, output_tokens=output_tokens)

    def _metered(self, event):
        return event

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        yield self._metered(usage_metadata(self.usage))
        async for event in super().structured_output(
            output_model, prompt, system_prompt=system_prompt, **kwargs
        ):
            yield event


class NestedMetadataModel(MeteredPlaybackModel):
    def _metered(self, event):
        return {"event": event}


async def record_registry(
    reporter: ConformanceReporter,
    clock: RampClock,
    samples: int,
    input_tokens: int = 1200,
    output_tokens: int = 400,
) -> None:
    for probe in build_registry():
        for sample in range(1, samples + 1):
            model = MeteredPlaybackModel([PAYLOADS[probe.name]], input_tokens, output_tokens)
            reporter.record(await run_probe(model, probe, model_for(probe.role), clock), sample)
