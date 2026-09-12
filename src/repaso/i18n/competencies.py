from repaso.schemas.common import Lang

NAMES_ES = {
    "math.g4.place_value.to_10000": "valor posicional hasta diez mil",
    "math.g4.fractions.equivalence": "fracciones equivalentes",
    "math.g4.fractions.addition_same_denominator": "suma de fracciones con igual denominador",
    "math.g4.multiplication.multi_digit": "multiplicación de varias cifras",
    "math.g4.fractions.comparison": "comparación de fracciones",
    "math.g4.division.with_remainder": "división con residuo",
    "math.g4.decimals.tenths_hundredths": "décimas y centésimas",
    "math.g4.geometry.area_rectangles": "área de rectángulos",
    "math.g4.measurement.length_conversion": "conversión de unidades de longitud",
    "math.g4.word_problems.two_step": "problemas de dos pasos",
    "math.g4.geometry.angle_types": "tipos de ángulos",
    "math.g4.data.line_plots": "gráficos de puntos con fracciones",
    "math.g4.numeration.number_sets": "naturales, decimales y fracciones",
    "math.g4.numeration.roman_numerals": "números romanos",
}


def competency_label(competency, lang):
    return NAMES_ES.get(competency.id, competency.name) if lang is Lang.ES else competency.name
