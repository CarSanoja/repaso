import pytest

from repaso.tools.knowledge import LocalTaxonomyRetriever, wording
from repaso.tools.lexical_ranking import tokenize
from tests.material_corpus import HISTORY_EN
from tests.material_corpus_languages import (
    ON_SUBJECT_LANGUAGES,
    READING_RU,
    WORKSHEET_AR,
    WORKSHEET_RU,
    WORKSHEET_ZH,
)

OWN_WORD = {
    "worksheet_ar": "الرياضيات",
    "worksheet_fr": "mathematiques",
    "worksheet_ru": "математика",
    "worksheet_zh": "数学",
}

NON_LATIN = {
    "worksheet_ar": WORKSHEET_AR,
    "worksheet_ru": WORKSHEET_RU,
    "worksheet_zh": WORKSHEET_ZH,
}


@pytest.fixture
def retriever() -> LocalTaxonomyRetriever:
    return LocalTaxonomyRetriever()


def top(retriever: LocalTaxonomyRetriever, page: str) -> float:
    matches = retriever.retrieve(page, grade=4, subject="math", limit=24)
    return matches[0].confidence if matches else 0.0


def slate_tokens(retriever: LocalTaxonomyRetriever) -> set[str]:
    tokens: set[str] = set()
    for competency in retriever.list_competencies(4, "math"):
        tokens |= tokenize(wording(competency))
    return tokens


@pytest.mark.parametrize("name", sorted(NON_LATIN))
def test_a_non_latin_maths_page_shares_only_digits_with_the_curriculum(retriever, name):
    shared = tokenize(NON_LATIN[name]) & slate_tokens(retriever)

    assert shared == {"1", "2", "3", "4"}


def test_the_hint_scores_a_russian_reading_page_as_high_as_a_russian_maths_page(retriever):
    assert top(retriever, READING_RU) >= top(retriever, WORKSHEET_RU)


def test_an_english_off_subject_page_outranks_every_non_latin_maths_page(retriever):
    history = top(retriever, HISTORY_EN)

    assert history > 0.0
    assert all(history > top(retriever, page) for page in NON_LATIN.values())


@pytest.mark.parametrize("name,word", sorted(OWN_WORD.items()))
def test_the_tokenizer_keeps_a_word_written_in_each_added_script(name, word):
    assert word in tokenize(ON_SUBJECT_LANGUAGES[name])
