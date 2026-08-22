import json

import pytest

from repaso.config.settings import Settings
from repaso.schemas.competency import Competency
from repaso.tools.knowledge import (
    DEFAULT_TAXONOMY_PATH,
    KnowledgeRetriever,
    LocalTaxonomyRetriever,
    build_knowledge_retriever,
    local_taxonomy_path,
    tokenize,
)

EQUIVALENCE = "math.g4.fractions.equivalence"


@pytest.fixture
def retriever() -> LocalTaxonomyRetriever:
    return LocalTaxonomyRetriever()


def test_equivalent_fraction_query_ranks_equivalence_first(retriever):
    matches = retriever.retrieve("equivalent fractions 2/4 = 1/2", grade=4, subject="math")
    assert matches
    assert matches[0].competency_id == EQUIVALENCE
    assert matches[0].confidence == pytest.approx(1.0)
    assert matches[0].confidence > matches[1].confidence


def test_grade_filter_excludes_other_grades(retriever):
    matches = retriever.retrieve("fractions with a common denominator", grade=5, subject="math")
    assert matches
    assert all(match.competency_id.startswith("math.g5.") for match in matches)


def test_subject_filter_returns_nothing_for_unknown_subject(retriever):
    assert retriever.retrieve("fractions", grade=4, subject="science") == []


def test_limit_is_respected(retriever):
    unlimited = retriever.retrieve("fractions", grade=4, subject="math")
    limited = retriever.retrieve("fractions", grade=4, subject="math", limit=2)
    assert len(unlimited) > 2
    assert len(limited) == 2
    assert limited == unlimited[:2]


def test_invalid_limit_is_rejected(retriever):
    with pytest.raises(ValueError):
        retriever.retrieve("fractions", grade=4, subject="math", limit=0)


def test_ties_break_by_competency_id(retriever):
    matches = retriever.retrieve("fractions", grade=4, subject="math")
    tied = [match.competency_id for match in matches if match.confidence == matches[0].confidence]
    assert tied == sorted(tied)


def test_ordering_is_deterministic_across_calls(retriever):
    first = retriever.retrieve("two step word problems about time", grade=4, subject="math")
    second = retriever.retrieve("two step word problems about time", grade=4, subject="math")
    third = LocalTaxonomyRetriever().retrieve(
        "two step word problems about time", grade=4, subject="math"
    )
    assert first == second == third


def test_unrelated_query_returns_no_matches(retriever):
    assert retriever.retrieve("photosynthesis chloroplast", grade=4, subject="math") == []


def test_get_competency_returns_full_record(retriever):
    competency = retriever.get_competency(EQUIVALENCE)
    assert isinstance(competency, Competency)
    assert competency.grade == 4
    assert competency.subject == "math"
    assert "fraction" in competency.name.lower()


def test_get_competency_is_none_for_unknown_id(retriever):
    assert retriever.get_competency("math.g9.calculus.limits") is None


def test_list_competencies_is_filtered_and_sorted(retriever):
    grade_three = retriever.list_competencies(grade=3, subject="math")
    assert len(grade_three) >= 5
    assert all(competency.grade == 3 for competency in grade_three)
    assert [competency.id for competency in grade_three] == sorted(
        competency.id for competency in grade_three
    )


def test_fixture_covers_primary_grades_and_is_unique():
    entries = json.loads(DEFAULT_TAXONOMY_PATH.read_text(encoding="utf-8"))
    ids = [entry["id"] for entry in entries]
    assert len(ids) == len(set(ids))
    assert len(ids) >= 20
    assert {entry["grade"] for entry in entries} == {3, 4, 5}
    assert all(entry["subject"] == "math" for entry in entries)


def test_tokenize_drops_punctuation_and_stopwords():
    assert tokenize("The area of a Rectangle!") == {"area", "rectangle"}


def test_custom_taxonomy_path_is_used(tmp_path):
    path = tmp_path / "tiny.json"
    path.write_text(
        json.dumps(
            [
                {
                    "id": "math.g4.custom.one",
                    "subject": "math",
                    "grade": 4,
                    "name": "Custom competency",
                    "description": "A single competency used only by this test.",
                }
            ]
        ),
        encoding="utf-8",
    )
    retriever = LocalTaxonomyRetriever(path)
    assert [competency.id for competency in retriever.list_competencies(4, "math")] == [
        "math.g4.custom.one"
    ]


def test_factory_returns_local_retriever(settings):
    retriever = build_knowledge_retriever(settings)
    assert isinstance(retriever, LocalTaxonomyRetriever)
    assert isinstance(retriever, KnowledgeRetriever)
    assert (
        retriever.retrieve("rounding to the nearest ten", grade=3, subject="math")[0].competency_id
        == "math.g3.rounding.nearest_ten"
    )


def test_factory_seeds_taxonomy_under_local_data_dir(settings):
    build_knowledge_retriever(settings)
    seeded = settings.local_data_dir / "curriculum" / DEFAULT_TAXONOMY_PATH.name
    assert seeded.exists()
    assert json.loads(seeded.read_text(encoding="utf-8")) == json.loads(
        DEFAULT_TAXONOMY_PATH.read_text(encoding="utf-8")
    )


def test_local_taxonomy_path_keeps_operator_edits(settings):
    first = local_taxonomy_path(settings)
    first.write_text(
        json.dumps(
            [
                {
                    "id": "math.g5.local.override",
                    "subject": "math",
                    "grade": 5,
                    "name": "Local override",
                    "description": "Replaces the packaged taxonomy for this environment.",
                }
            ]
        ),
        encoding="utf-8",
    )
    retriever = build_knowledge_retriever(settings)
    assert [competency.id for competency in retriever.list_competencies(5, "math")] == [
        "math.g5.local.override"
    ]


def test_factory_requires_knowledge_base_id_outside_local_mode():
    cloud = Settings(aws_region="us-east-1")
    with pytest.raises(ValueError):
        build_knowledge_retriever(cloud)
