from datetime import UTC, datetime

from repaso.agents.adaptation_policy import PolicySignals
from repaso.schemas.competency import Competency
from repaso.schemas.item import Item, ItemKind, ItemStatus
from repaso.schemas.provenance import Provenance, Source

GRADE = 4
SUBJECT = "matemática"
CREATED_AT = datetime(2026, 9, 1, 15, 0, tzinfo=UTC)

COMPETENCY = Competency(
    id="MAT-4-FRAC-EQUIV",
    subject=SUBJECT,
    grade=GRADE,
    name="Fracciones equivalentes",
    description=(
        "Reconoce y genera fracciones equivalentes multiplicando o dividiendo "
        "numerador y denominador por el mismo número, y las compara con material "
        "concreto y con la recta numérica."
    ),
)

MATERIAL_TEXT = (
    "Cuaderno de matemática, cuarto grado. Tema: fracciones equivalentes.\n"
    "Dos fracciones son equivalentes cuando representan la misma parte del entero. "
    "Para obtener una fracción equivalente multiplicamos el numerador y el "
    "denominador por el mismo número distinto de cero.\n"
    "Ejemplo trabajado en clase: 1/2 = 2/4 porque 1x2 = 2 y 2x2 = 4.\n"
    "Ejercicios de la página 47:\n"
    "1) Completa: 3/4 = 6/__\n"
    "2) Pinta 2/3 de la barra y luego 4/6 de otra barra igual. ¿Qué observas?\n"
    "3) Escribe dos fracciones equivalentes a 1/5.\n"
    "4) Explica con tus palabras por qué 5/10 y 1/2 nombran la misma cantidad."
)

def _candidate(key: str, name: str, description: str) -> Competency:
    return Competency(id=key, subject=SUBJECT, grade=GRADE, name=name, description=description)


CANDIDATES = (
    COMPETENCY,
    _candidate(
        "MAT-4-FRAC-COMPARA",
        "Comparación de fracciones",
        "Ordena fracciones de igual y distinto denominador.",
    ),
    _candidate(
        "MAT-4-DECIM-INTRO",
        "Décimos y centésimos",
        "Lee y escribe números decimales hasta el centésimo.",
    ),
    _candidate(
        "MAT-4-MULT-2CIF",
        "Multiplicación por dos cifras",
        "Resuelve multiplicaciones con reagrupación.",
    ),
)

MCQ_ITEM = Item(
    id="item-frac-equiv-1",
    competency_id=COMPETENCY.id,
    kind=ItemKind.MCQ,
    difficulty=2,
    stem="Según la página del cuaderno, ¿cuál fracción es equivalente a 3/4?",
    options=["6/8", "3/8", "4/3", "7/8"],
    answer_key="6/8",
    rationale="Multiplicamos numerador y denominador por 2: 3x2 = 6 y 4x2 = 8.",
    status=ItemStatus.CANDIDATE,
    provenance=Provenance(source=Source.GENERATED, created_at=CREATED_AT),
)

OPEN_ITEM = Item(
    id="item-frac-equiv-2",
    competency_id=COMPETENCY.id,
    kind=ItemKind.OPEN,
    difficulty=3,
    stem="Explica con tus palabras por qué 5/10 y 1/2 nombran la misma cantidad.",
    answer_key="Porque 5/10 se obtiene multiplicando 1/2 por 5 arriba y abajo.",
    rationale="La equivalencia se conserva al multiplicar ambos términos por el mismo número.",
    rubric=(
        "2 puntos: nombra la misma cantidad y justifica con la multiplicación o "
        "división de ambos términos. 1 punto: afirma la equivalencia sin justificarla. "
        "0 puntos: dice que son distintas o no responde."
    ),
    status=ItemStatus.CANDIDATE,
    provenance=Provenance(source=Source.GENERATED, created_at=CREATED_AT),
)

STUDENT_ANSWER = "Porque si parto la mitad en cinco pedacitos me quedan 5 de 10, es lo mismo."

SIGNALS = PolicySignals(
    struggle=False,
    disengaged=False,
    fast_guessing=False,
    ema_accuracy=0.62,
    streak=1,
    attempts=11,
)

EVIDENCE_COUNT = 9
