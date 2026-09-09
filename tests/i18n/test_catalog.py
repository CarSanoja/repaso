import re

import pytest

from repaso.i18n.catalog import known_keys, msg
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


def test_consent_states_both_retention_windows():
    for lang in (Lang.ES, Lang.EN):
        consent = msg("consent", lang)
        assert "7" in consent and "35" in consent


def test_no_student_facing_message_asks_for_real_names():
    for key in known_keys():
        for catalog in (EN, ES):
            lowered = catalog[key].lower()
            assert "full name" not in lowered
            assert "nombre completo" not in lowered
