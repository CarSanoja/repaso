import pytest
from pydantic import BaseModel, ValidationError
from strands.tools import convert_pydantic_to_tool_spec

from repaso.agents.grader import OpenGrade
from repaso.agents.item_critic import CriticFinding
from repaso.agents.item_generator import ItemDraft
from tests.live.registry import build_registry
from tests.tools.live_fixtures import PAYLOADS

DRAFT = PAYLOADS["GeneratedBatch"]["items"][0]


def schemas_and_payloads() -> list[tuple[type[BaseModel], dict]]:
    pairs = [(probe.output_schema, PAYLOADS[probe.name]) for probe in build_registry()]
    return [*pairs, (ItemDraft, DRAFT)]


def published(schema: type[BaseModel]) -> dict:
    return convert_pydantic_to_tool_spec(schema)["inputSchema"]["json"]


def offered_as_null(schema: type[BaseModel]) -> set[str]:
    properties = published(schema).get("properties", {})
    return {name for name, shape in properties.items() if "null" in shape.get("type", "")}


CASES = schemas_and_payloads()
CASE_IDS = [schema.__name__ for schema, _ in CASES]


@pytest.mark.parametrize(("schema", "payload"), CASES, ids=CASE_IDS)
def test_every_field_the_tool_spec_offers_as_null_is_accepted_as_null(schema, payload):
    spec = published(schema)
    offered = offered_as_null(schema)
    assert offered | set(spec.get("required", [])) == set(spec["properties"])
    for field in offered:
        schema(**{**payload, field: None})


@pytest.mark.parametrize(("schema", "payload"), CASES, ids=CASE_IDS)
def test_a_required_field_is_still_an_error_when_it_arrives_null(schema, payload):
    for field in published(schema).get("required", []):
        with pytest.raises(ValidationError):
            schema(**{**payload, field: None})


def test_a_null_collection_reads_as_nothing_rather_than_as_missing():
    draft = ItemDraft(**{**DRAFT, "options": None})
    finding = CriticFinding(accepted=True, flaws=None, notes=None)

    assert draft.options == []
    assert finding.flaws == []
    assert finding.notes == ""


def test_a_collection_that_is_not_a_collection_is_still_rejected():
    with pytest.raises(ValidationError):
        ItemDraft(**{**DRAFT, "options": "6/8"})
    with pytest.raises(ValidationError):
        CriticFinding(accepted=True, flaws="ambiguous")


def test_the_closed_and_the_bounded_stay_closed_and_bounded():
    with pytest.raises(ValidationError):
        ItemDraft(**{**DRAFT, "kind": "essay"})
    with pytest.raises(ValidationError):
        OpenGrade(correct=True, rubric_points=3.0, confidence=0.9, feedback="bien")
    with pytest.raises(ValidationError):
        OpenGrade(correct=True, rubric_points=1.0, confidence=1.4, feedback="bien")
