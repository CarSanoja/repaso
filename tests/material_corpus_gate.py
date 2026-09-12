RECEIPT_ES = """SUPERMERCADO LA ESQUINA
Caja 3 Ticket 004812
Harina de trigo 1 kg 2 x 1,45 2,90
Leche entera litro 3 x 1,10 3,30
Huevos carton de 12 2,75
Detergente 1,5 L 4,20
Subtotal 13,15
IVA 16% 2,10
TOTAL 15,25
Gracias por su compra"""

MEDICINE_BOX_EN = """PARACETAMOL 500 mg tablets
Read the leaflet before use. Keep out of reach of children.
Adults and children over 12: one or two tablets every 4 to 6 hours.
Do not take more than 8 tablets in 24 hours.
Batch L4429 Expiry 09 2027
Store below 25 C in the original carton"""

FIRST_GRADE_ES = """Matematica primer grado
Sumas hasta 10
1. Cuenta los dibujos y escribe cuantos hay.
2 + 3 = ___
4 + 1 = ___
5 + 5 = ___
2. Dibuja la cantidad que falta para llegar a 10.
3. Encierra el numero mayor de cada pareja.
7 y 4      2 y 6"""

NINTH_GRADE_ES = """Matematica noveno grado
Ecuaciones de segundo grado
1. Resuelve por la formula general.
x^2 - 5x + 6 = 0
2x^2 + 3x - 2 = 0
2. Calcula el discriminante y di cuantas soluciones reales tiene.
3. Factoriza y comprueba las raices.
4. Aplica el teorema de Pitagoras al triangulo de la figura."""

UNCOVERED_TOPIC_ES = """Matematica cuarto grado
Probabilidad: seguro, posible, imposible
1. Lanza una moneda veinte veces y anota cuantas caras salen.
2. En una bolsa hay 3 bolas rojas y 5 azules. Al sacar una sin mirar,
que color es mas probable? Explica por que.
3. Clasifica cada suceso en seguro, posible o imposible.
4. Dibuja una ruleta donde ganar sea imposible."""

OCR_NOISE = """lll  .  ,  ~~  |||
rn rn  vv  ..  ---
o0o  ||  '' ''  ,,,,
.  .    .   ..  .
tt  ll  ii  ..  ~"""

BLANK_PAGE = "   \n\n   \n"

NOT_SCHOOLWORK = {
    "medicine_box_en": MEDICINE_BOX_EN,
    "receipt_es": RECEIPT_ES,
}

WRONG_GRADE = {
    "first_grade_es": FIRST_GRADE_ES,
    "ninth_grade_es": NINTH_GRADE_ES,
}

UNCOVERED = {
    "uncovered_topic_es": UNCOVERED_TOPIC_ES,
}

UNREADABLE = {
    "blank_page": BLANK_PAGE,
    "ocr_noise": OCR_NOISE,
}

GATE_CORPUS = {**NOT_SCHOOLWORK, **WRONG_GRADE, **UNCOVERED, **UNREADABLE}
