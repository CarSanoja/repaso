import re

import pytest

from repaso.i18n.catalog import counted, known_keys, msg
from repaso.i18n.en import MESSAGES as EN
from repaso.i18n.es import MESSAGES as ES
from repaso.schemas.common import Lang

PLACEHOLDER = re.compile(r"\{(\w+)\}")


def test_both_catalogs_cover_the_same_keys():
    assert set(EN) == set(ES)


def test_placeholders_match_across_languages():
    for key in known_keys():
        assert set(PLACEHOLDER.findall(EN[key])) == set(PLACEHOLDER.findall(ES[key])), key


def test_formatting_fills_placeholders():
    text = msg("enrollment_done", Lang.ES, alias="Leo", time="7pm")
    assert "Leo" in text
    assert "7pm" in text
    assert "{" not in text


def test_spanish_is_served_for_spanish_families():
    assert "práctica" in msg("welcome", Lang.ES).lower()


def test_unknown_key_raises():
    with pytest.raises(KeyError):
        msg("does_not_exist", Lang.ES)


def test_consent_states_the_hard_rules():
    for lang in (Lang.ES, Lang.EN):
        consent = msg("consent", lang).lower()
        assert "/forget" in consent
        assert "alias" in consent


def test_consent_names_everything_enrollment_goes_on_to_ask_for():
    asked = {
        Lang.ES: ("colegio", "secci", "hora de práctica", "examen"),
        Lang.EN: ("school", "section", "practice time", "exam"),
    }
    for lang, expected in asked.items():
        consent = msg("consent", lang).lower()
        for item in expected:
            assert item in consent, (lang, item)


def test_consent_says_the_words_go_and_the_attempt_stays():
    expected = {Lang.ES: ("7 días", "el intento"), Lang.EN: ("7 days", "the attempt")}
    for lang, phrases in expected.items():
        consent = msg("consent", lang).lower()
        for phrase in phrases:
            assert phrase in consent, (lang, phrase)


def test_consent_states_both_retention_windows():
    for lang in (Lang.ES, Lang.EN):
        consent = msg("consent", lang)
        assert "7" in consent and "35" in consent


def test_the_sitting_tells_the_child_who_reads_the_chat():
    expected = {Lang.ES: ("chat", "lee"), Lang.EN: ("chat", "read")}
    for lang, phrases in expected.items():
        opening = msg("study_who_reads", lang).lower()
        for phrase in phrases:
            assert phrase in opening, (lang, phrase)


def test_no_student_facing_message_asks_for_real_names():
    for key in known_keys():
        for catalog in (EN, ES):
            lowered = catalog[key].lower()
            assert "full name" not in lowered
            assert "nombre completo" not in lowered


def test_a_count_of_one_picks_the_singular_wording():
    for lang in (Lang.ES, Lang.EN):
        assert counted("status_topics", lang, 1) == msg("status_topics_one", lang)
        assert counted("status_topics", lang, 2) == msg("status_topics", lang, count=2)


def test_every_singular_variant_has_a_plural_to_fall_back_to():
    for key in known_keys():
        if key.endswith("_one"):
            assert key.removesuffix("_one") in known_keys(), key


def test_no_family_facing_line_says_one_of_a_plural_noun():
    plurals = ("preguntas", "temas", "días", "correctas", "questions", "topics", "days")
    for key in known_keys():
        if not key.endswith("_one"):
            continue
        for catalog in (EN, ES):
            words = catalog[key].split()
            for index, word in enumerate(words[:-1]):
                if word == "1":
                    assert words[index + 1].strip(".,") not in plurals, (key, catalog[key])


PLURAL_IMPERATIVES = ("escriban", "manden", "mándenme", "toquen", "envíen")


def test_a_command_is_asked_of_the_one_person_who_types_it():
    for key in known_keys():
        if "/" not in ES[key]:
            continue
        for form in PLURAL_IMPERATIVES:
            assert form not in ES[key].lower(), (key, form)
