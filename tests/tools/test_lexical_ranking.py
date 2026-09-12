from repaso.tools.lexical_ranking import coverage, rank, token_weights, tokenize

DOCUMENTS = {
    "fractions": "Equivalent fractions. Recognize and generate equivalent fractions.",
    "decimals": "Decimals to tenths and hundredths. Read and write decimal numbers.",
    "area": "Area of rectangles. Multiply the side lengths of a rectangle.",
}


def test_accented_letters_survive_tokenization():
    assert tokenize("matemática") == {"matematica"}
    assert tokenize("número") == {"numero"}
    assert tokenize("mayúsculas") == {"mayusculas"}
    assert tokenize("fracções") == {"fraccoes"}


def test_tokenizing_is_case_and_punctuation_insensitive():
    assert tokenize("The Area, of a Rectangle!") == {"the", "area", "of", "a", "rectangle"}


def test_two_spellings_of_the_same_word_meet_in_the_same_token():
    assert tokenize("numérico") == tokenize("NUMERICO")


def test_a_word_every_document_uses_carries_no_weight():
    weights = token_weights([{"fractions", "the"}, {"decimals", "the"}, {"area", "the"}])
    assert weights["the"] == 0.0
    assert weights["fractions"] > 0.0


def test_a_rare_word_outweighs_a_common_one():
    weights = token_weights([{"the", "fractions"}, {"the", "area"}, {"the", "angles"}])
    assert weights["fractions"] > weights["the"]


def test_coverage_is_the_share_of_a_document_the_query_echoes():
    weights = {"fractions": 1.0, "equivalent": 1.0}
    assert coverage({"fractions"}, {"fractions", "equivalent"}, weights) == 0.5
    assert coverage({"fractions", "equivalent"}, {"fractions", "equivalent"}, weights) == 1.0
    assert coverage(set(), {"fractions"}, weights) == 0.0


def test_a_document_of_only_weightless_words_scores_zero():
    weights = {"the": 0.0}
    assert coverage({"the"}, {"the"}, weights) == 0.0


def test_padding_a_query_does_not_lower_the_score_of_what_it_matches():
    short = dict(rank("equivalent fractions", DOCUMENTS))
    padded_query = "equivalent fractions " + " ".join(f"ejercicio{n}" for n in range(200))
    padded = dict(rank(padded_query, DOCUMENTS))
    assert padded["fractions"] == short["fractions"]


def test_ranking_is_ordered_and_ties_break_by_key():
    ranked = rank("nothing here matches", DOCUMENTS)
    assert [score for _, score in ranked] == sorted((s for _, s in ranked), reverse=True)
    assert [key for key, _ in ranked] == sorted(DOCUMENTS)


def test_ranking_returns_every_document_it_was_given():
    assert {key for key, _ in rank("fractions", DOCUMENTS)} == set(DOCUMENTS)


def test_scores_stay_inside_the_unit_interval():
    for _, score in rank("fractions decimals area rectangle tenths", DOCUMENTS):
        assert 0.0 <= score <= 1.0
