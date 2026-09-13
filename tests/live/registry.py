from pydantic import BaseModel

from repaso.agents.adaptation_policy import PolicyDecision, signals_prompt
from repaso.agents.answerability_probe import ProbeAnswer, render_blind
from repaso.agents.capsule_composer import Snippet
from repaso.agents.competency_mapper import MappingDecision, request_text
from repaso.agents.escalation_composer import TeacherNote
from repaso.agents.explainer import explain_prompt
from repaso.agents.grader import OpenGrade, open_prompt
from repaso.agents.intake_screener import IntakeDecision, frame_untrusted
from repaso.agents.item_critic import FLAW_VOCABULARY, CriticFinding, render_review
from repaso.agents.item_generator import LANGUAGE_NAMES, GeneratedBatch
from repaso.agents.prompts import (
    adaptation_policy,
    answerability_probe,
    capsule_composer,
    escalation_composer,
    grader,
    intake_screener,
)
from repaso.agents.prompts import competency_mapper as mapper_prompt
from repaso.agents.prompts import explainer as explainer_prompt
from repaso.agents.prompts import item_critic as critic_prompt
from repaso.agents.prompts import item_generator as generator_prompt
from repaso.agents.prompts import turn_reader as turn_reader_prompt
from repaso.agents.turn_reader import briefing
from repaso.config.models import ModelRole
from repaso.schemas.common import FrozenStrictModel, Lang
from repaso.schemas.turn import Explanation, TurnDecision
from tests.live import samples

MAPPING_LIMIT = 3
ITEMS_PER_BATCH = 4
LANG = Lang.ES


class SchemaProbe(FrozenStrictModel):
    role: ModelRole
    output_schema: type[BaseModel]
    system: str
    prompt: str

    @property
    def name(self) -> str:
        return self.output_schema.__name__


def mapping_prompt() -> str:
    return request_text(samples.MATERIAL_TEXT, list(samples.CANDIDATES), MAPPING_LIMIT)


def _generation_prompt() -> str:
    competency = samples.COMPETENCY
    return (
        f"Competency: {competency.id} — {competency.name}\n"
        f"What it means: {competency.description}\n"
        f"Write exactly {ITEMS_PER_BATCH} items for this competency.\n"
        f"Write every word the family reads — stem, options, answer_key, rationale and "
        f"rubric — in {LANGUAGE_NAMES[LANG]}.\n\n"
        f"Material:\n{samples.MATERIAL_TEXT}"
    )


def _snippet_prompt() -> str:
    competency = samples.COMPETENCY
    return (
        f"Language code: {LANG.value}\n"
        f"Subject: {competency.subject}\n"
        f"School grade: {competency.grade}\n"
        f"Competency: {competency.name}\n"
        f"What it covers: {competency.description}\n"
        f"Write the reminder in {LANG.value}."
    )


def build_registry() -> tuple[SchemaProbe, ...]:
    return (
        SchemaProbe(
            role=ModelRole.CLASSIFY,
            output_schema=IntakeDecision,
            system=intake_screener.SYSTEM,
            prompt=frame_untrusted(samples.MATERIAL_TEXT),
        ),
        SchemaProbe(
            role=ModelRole.STRUCTURED,
            output_schema=MappingDecision,
            system=mapper_prompt.SYSTEM.format(
                grade=samples.GRADE, subject=samples.SUBJECT, limit=MAPPING_LIMIT
            ),
            prompt=mapping_prompt(),
        ),
        SchemaProbe(
            role=ModelRole.STRUCTURED,
            output_schema=PolicyDecision,
            system=adaptation_policy.SYSTEM,
            prompt=signals_prompt(samples.SIGNALS),
        ),
        SchemaProbe(
            role=ModelRole.GENERATE,
            output_schema=GeneratedBatch,
            system=generator_prompt.SYSTEM.format(grade=samples.GRADE),
            prompt=_generation_prompt(),
        ),
        SchemaProbe(
            role=ModelRole.GENERATE,
            output_schema=Snippet,
            system=capsule_composer.SYSTEM,
            prompt=_snippet_prompt(),
        ),
        SchemaProbe(
            role=ModelRole.GENERATE,
            output_schema=TeacherNote,
            system=escalation_composer.SYSTEM,
            prompt=escalation_composer.STRUGGLE_REQUEST.format(
                lang=LANG.value,
                competency=samples.COMPETENCY.name,
                evidence_count=samples.EVIDENCE_COUNT,
            ),
        ),
        SchemaProbe(
            role=ModelRole.JUDGE,
            output_schema=CriticFinding,
            system=critic_prompt.SYSTEM.format(grade=samples.GRADE, flaws=FLAW_VOCABULARY),
            prompt=render_review(samples.MCQ_ITEM, samples.MATERIAL_TEXT, samples.GRADE),
        ),
        SchemaProbe(
            role=ModelRole.JUDGE,
            output_schema=OpenGrade,
            system=grader.SYSTEM.format(lang=LANG.value),
            prompt=open_prompt(samples.OPEN_ITEM, samples.STUDENT_ANSWER, LANG),
        ),
        SchemaProbe(
            role=ModelRole.STRUCTURED,
            output_schema=TurnDecision,
            system=f"{turn_reader_prompt.SYSTEM.format(lang=LANG.value)}\n{briefing(samples.TURN_CONTEXT)}",
            prompt=samples.TURN_MESSAGE,
        ),
        SchemaProbe(
            role=ModelRole.GENERATE,
            output_schema=Explanation,
            system=explainer_prompt.SYSTEM.format(grade=samples.GRADE, lang=LANG.value),
            prompt=explain_prompt(samples.EXPLAIN_CONTEXT),
        ),
        SchemaProbe(
            role=ModelRole.PROBE,
            output_schema=ProbeAnswer,
            system=answerability_probe.SYSTEM,
            prompt=render_blind(samples.MCQ_ITEM),
        ),
    )
