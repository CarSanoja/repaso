import json

import pytest
from pydantic import ValidationError

from repaso.agents.competency_mapper import MappingDecision
from repaso.agents.intake_screener import IntakeDecision
from repaso.agents.item_critic import CriticFinding
from repaso.agents.item_generator import GeneratedBatch, ItemDraft, is_valid_draft
from tests.tools.live_fixtures import PAYLOADS

DRAFT = PAYLOADS["GeneratedBatch"]["items"][0]


def test_a_batch_encoded_as_text_carries_the_same_drafts_as_a_batch_of_objects():
    drafts = [DRAFT, {**DRAFT, "stem": "Completa: 2/5 = ?/10"}]

    batch = GeneratedBatch(items=json.dumps(drafts, ensure_ascii=False))

    assert [draft.stem for draft in batch.items] == [DRAFT["stem"], "Completa: 2/5 = ?/10"]
    assert all(is_valid_draft(draft) for draft in batch.items)


def test_the_short_collections_decode_from_text_too():
    assert ItemDraft(**{**DRAFT, "options": '["2/4", "1/3", "3/5"]'}).options == [
        "2/4",
        "1/3",
        "3/5",
    ]
    assert CriticFinding(accepted=False, flaws='["ambiguous"]').flaws == ["ambiguous"]
    assert IntakeDecision(safe=True, reasons="[]").reasons == []
    assert MappingDecision(competency_ids='["math.g4.fractions.equivalence"]').competency_ids == [
        "math.g4.fractions.equivalence"
    ]


def test_text_that_is_not_a_collection_is_still_rejected():
    with pytest.raises(ValidationError):
        ItemDraft(**{**DRAFT, "options": "6/8"})
    with pytest.raises(ValidationError):
        CriticFinding(accepted=True, flaws="ambiguous")
    with pytest.raises(ValidationError):
        GeneratedBatch(items='{"stem": "Completa: 1/2 = ?/4"}')
    with pytest.raises(ValidationError):
        GeneratedBatch(items="null")


def test_a_decoded_collection_is_validated_like_any_other():
    with pytest.raises(ValidationError):
        GeneratedBatch(items=json.dumps([{**DRAFT, "kind": "essay"}]))
    with pytest.raises(ValidationError):
        ItemDraft(**{**DRAFT, "options": "[1, 2, 3]"})
