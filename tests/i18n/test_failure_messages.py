import pytest

from repaso.i18n.catalog import msg
from repaso.schemas.common import Lang

FAILURES = (
    "material_unmatched",
    "material_held",
    "material_interrupted",
    "material_thin",
    "material_unusable",
    "material_unreadable",
    "media_unreadable",
    "rephoto_request",
)

BLAME = ("tu hijo", "tu hija", "el niño", "la niña", "your child", "the child", "your kid")
USTED = ("usted", "envíe", "mande", "tome de nuevo", "reenvíe")
HEDGED = ("puede", "may ", "might")


def rendered(key: str, lang: Lang) -> str:
    return msg(key, lang, grade=4).lower()


@pytest.mark.parametrize("key", FAILURES)
@pytest.mark.parametrize("lang", [Lang.ES, Lang.EN])
def test_no_failure_message_blames_a_child(key, lang):
    text = rendered(key, lang)

    assert not any(blame in text for blame in BLAME)


@pytest.mark.parametrize("key", FAILURES)
def test_every_spanish_failure_message_keeps_the_tu_register(key):
    text = rendered(key, Lang.ES)

    assert not any(formal in text for formal in USTED)


@pytest.mark.parametrize("lang", [Lang.ES, Lang.EN])
def test_a_rephoto_request_hedges_why_the_reading_was_poor(lang):
    text = rendered("rephoto_request", lang)

    assert any(hedge in text for hedge in HEDGED)
    assert "borrosa" not in text
    assert "came out blurry" not in text


@pytest.mark.parametrize("lang", [Lang.ES, Lang.EN])
def test_an_unfetched_file_is_not_called_a_truncated_one(lang):
    text = rendered("media_unreadable", lang)

    assert "completo" not in text
    assert "whole" not in text
