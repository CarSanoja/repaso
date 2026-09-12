import json

from repaso.i18n.competencies import NAMES_ES
from repaso.schemas.competency import Competency
from repaso.tools.knowledge import DEFAULT_TAXONOMY_PATH

NUMBER_SETS = "math.g4.numeration.number_sets"
ROMAN_NUMERALS = "math.g4.numeration.roman_numerals"


def entries() -> list[dict]:
    return json.loads(DEFAULT_TAXONOMY_PATH.read_text(encoding="utf-8"))


def test_fourth_grade_covers_the_number_sets_a_numeration_page_works_on():
    described = {entry["id"]: entry["description"] for entry in entries()}

    assert NUMBER_SETS in described
    for word in ("natural", "decimal", "fraction"):
        assert word in described[NUMBER_SETS].lower()


def test_fourth_grade_covers_the_roman_numeral_system():
    described = {entry["id"]: entry["description"] for entry in entries()}

    assert ROMAN_NUMERALS in described
    assert "roman numerals" in described[ROMAN_NUMERALS].lower()


def test_every_new_competency_is_a_well_formed_fourth_grade_record():
    records = {entry["id"]: Competency(**entry) for entry in entries()}

    for key in (NUMBER_SETS, ROMAN_NUMERALS):
        assert records[key].grade == 4
        assert records[key].subject == "math"


def test_the_family_reads_a_spanish_label_for_every_fourth_grade_competency():
    fourth = [entry["id"] for entry in entries() if entry["grade"] == 4]

    assert set(fourth) <= set(NAMES_ES)
