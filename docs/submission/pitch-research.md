# Investigación del pitch y decisiones de presentación

Registro de trabajo del 14 de septiembre de 2026. Audiencia: quien prepare el
producto, el video y la candidatura. Estas notas no certifican que las funciones
propuestas estén construidas ni que exista un piloto.

## Punto de partida y dirección actual

El objetivo del usuario es una candidatura competitiva a Devpost. «Listo» se
refiere a esa entrega. La validación de producción y un piloto con familias son
trabajos distintos y no deben convertirse en requisitos inventados del concurso.

La dirección elegida para desarrollar el pitch es **Good Neighbor Agents**:
comunicación escuela–familias y seguimiento de un grupo de aprendizaje, con
memoria persistente de lo ocurrido, las decisiones humanas y sus consecuencias.

El usuario manejará Telegram. El asistente preparará la segunda pantalla y las
instrucciones del recorrido. Esa respuesta no autoriza al asistente a enviar
mensajes a contactos ni a atribuir colaboraciones a escuelas u organizaciones.

El usuario pidió investigar el caso online: no se presupone acceso a un docente,
una organización aliada, participantes o testimonios propios. La demostración
utilizará personas y un centro ficticios, identificados como escenario sintético.

## Tesis del producto

**La memoria del aprendizaje entre la escuela y el hogar.**

Repaso conecta una fuente educativa con la práctica en casa, conserva evidencia
de las dificultades, ayuda a decidir dónde intervenir y permite comprobar qué
pasó después. La propuesta de valor comunitaria es que el seguimiento sobreviva
a los mensajes individuales y pueda ser utilizado por un adulto autorizado que
acompaña al grupo.

La memoria tiene tres componentes visibles:

- Lo acordado: material, objetivo y decisiones del adulto.
- Lo observado: intentos, resultados, revisiones y explicaciones utilizadas.
- Lo pendiente: intervención propuesta, responsable autorizado y siguiente paso.

Cada observación debe mostrar procedencia y fecha. Los campos de responsable y
el ciclo de aprobación docente son requisitos propuestos; no describen una
capacidad ya completa.

La originalidad que proponemos demostrar reside en el encadenamiento
**material → práctica → evidencia → decisión → acción → seguimiento**.
Memoria, mensajes a padres y agentes educativos tienen precedentes. No se ha
realizado una revisión exhaustiva de competidores ni se afirma exclusividad.

## Evolución del enfoque

| Enfoque explorado | Qué conservamos | Por qué no basta por sí solo |
| --- | --- | --- |
| Compañero que ayuda a estudiar | Conversación y práctica accesibles | No hace visible el trabajo comunitario ni el seguimiento |
| Rutina familiar automática / Everyday Agents | Programación, adaptación y control del padre | Presenta principalmente a una familia como beneficiaria |
| Banco de memoria y trazabilidad | Evidencia persistente y causa de cada cambio | Hay que mostrar una consecuencia útil, no solo almacenamiento |
| Refuerzo para quienes no pueden pagar clases | Motivación de acceso y costo medible | Falta una cifra local verificable de asequibilidad y una comparación equivalente con tutorías |
| Continuidad para niños fuera de la escuela | Necesidad documentada y rol del facilitador | La versión actual requiere conexión, adulto y material; no reemplaza la escuela |
| Escuela/comunidad–familias con seguimiento | Grupo, decisiones humanas y memoria con consecuencias | Requiere completar el acceso y la intervención del coordinador |

La recomendación concreta está en [good-neighbor-case.md](good-neighbor-case.md):
un pequeño grupo de recuperación de aprendizajes con un facilitador, comenzando
por matemática de cuarto grado.

## Fuentes verificadas y uso permitido en el relato

### 1. Un trabajo comunitario concreto: Zulia

UNICEF publicó el 3 de marzo de 2021 una crónica sobre trabajo de junio de 2020.
Describe facilitadores que daban seguimiento a **25 niños cada uno** mediante
visitas, WhatsApp o SMS cuando existía acceso, y actividades en centros
comunitarios. Había guías de lectura y pensamiento matemático.

Uso: explicar un modelo de trabajo real que inspira el caso. La cifra es
histórica; no es la carga actual verificada de un facilitador ni una cantidad de
usuarios de Repaso. No atribuir Telegram a este programa.

[Fuente primaria: UNICEF](https://www.unicef.org/venezuela/en/stories/education-cannot-wait-programme-doesnt-stop-during-quarantine).

### 2. Necesidad y respuesta recientes en Venezuela

El informe de UNICEF de cierre de 2025, publicado en enero de 2026, estima
**2,7 millones de niños con necesidad de apoyo educativo** y **1,5 millones
fuera de la escuela**. Registra programas de recuperación que alcanzaron a
4.073 niños fuera del sistema y 1.511 reintegraciones, con participación de Fe y
Alegría y ASEINC. Son cifras del programa y del contexto, no efectos de Repaso.

Uso: una cifra local y fechada en la apertura; el modelo de acompañamiento como
referencia. Ninguna de esas entidades es una aliada confirmada de Repaso.

[Fuente primaria: UNICEF, página 6](https://www.unicef.org/media/178481/file/Venezuela-Humanitarian-SitRep-No.2-(End-of-Year),-31-December-2025.pdf.pdf).

### 3. Evidencia experimental del mecanismo: Papás al Día

La síntesis de J-PAL describe aproximadamente 1.000 niños de siete escuelas de
bajos ingresos en Chile. Informar regularmente por SMS a los padres produjo
una mejora de **0,09 desviaciones estándar en notas de matemáticas** y una
reducción de **2,7 puntos porcentuales en reprobar matemáticas**. El estudio
también reporta mejoras de asistencia.

Uso: fundamentar la hipótesis de que información oportuna puede servir a las
familias. Fue una intervención de SMS en otro contexto, no un ensayo de IA ni de
Repaso. No trasladar sus efectos al producto. Borradores anteriores del trabajo
tienen otras muestras; mantener los denominadores de la versión citada.

[J-PAL: evaluación](https://www.povertyactionlab.org/evaluation/reducing-parent-school-information-gaps-and-improving-education-outcomes-evidence-high).
[BID: explicación de los investigadores, 2021](https://www.iadb.org/en/blog/research-development/text-messaging-parents-boost-student-performance).

### 4. Acceso desigual al refuerzo privado

UNESCO explica que el ingreso y la ubicación geográfica condicionan el acceso a
tutorías privadas, y que la brecha digital limita las alternativas online.
No encontramos en esta investigación una proporción local verificable de
familias venezolanas que no pueden pagar clases adicionales.

Uso: motivación cualitativa. No inventar precio promedio de una clase, ahorro
familiar, equivalencia con tutorías ni tamaño de mercado atendible.

[UNESCO: Private supplementary tutoring, noviembre de 2025](https://www.unesco.org/en/articles/what-you-need-know-about-private-supplementary-tutoring).

### 5. Contexto global opcional

El informe GEM 2026 sitúa en **273 millones** la población fuera de la escuela
en **2024**, incluyendo 79 millones en edad de primaria. Sustituye como
referencia más reciente a la cifra de 272 millones para 2023 difundida en 2025.

Uso: contexto global si hace falta; preferir el dato local para el video. No
presentar el total global como mercado alcanzable por Telegram.

[UNESCO: seguimiento de los ODS, GEM 2026](https://www.unesco.org/reports/gem-report/en/2026-monitoring-sdg4).

### Datos que no trasladaremos al pitch

No usar la caída de matrícula del 46% de informes anteriores sin aclarar su base.
Las notas periodísticas consultadas discrepan al describir la regularidad de
asistencia de ENCOVI 2025; el PDF primario no se pudo abrir con el lector web.
Se excluyeron esas cifras del argumento seleccionado. Tampoco se utilizarán
estadísticas de lectura como si midieran dominio matemático.

## Criterios del concurso traducidos a pruebas del producto

| Criterio | Qué debe verse |
| --- | --- |
| Implementación técnica | Un mensaje real activa el flujo Strands/AgentCore y termina en estado persistido y efecto visible |
| Diseño | Padre y facilitador entienden qué hacer; pendientes, errores y revisiones tienen salida |
| Impacto potencial | Un trabajo documentado de seguimiento comunitario se completa con evidencia; métricas propias separadas de estudios externos |
| Creatividad | Una observación cambia una decisión posterior y conserva su procedencia |
| Presentación | Ambas pantallas cuentan el mismo caso; el resultado llega temprano y el cierre muestra cumplimiento |

Los cinco criterios tienen el mismo peso. La demo en vivo y AgentCore refuerzan
la implementación, pero son opcionales. El video admite diapositivas,
grabaciones y voz en off, dura como máximo cinco minutos y debe demostrar el
proyecto y explicar problema, público e importancia. YouTube/Vimeo público,
repositorio público con MIT/Apache, README, diagrama, Builder ID y materiales
en inglés o traducidos forman parte de la entrega. Debe ofrecerse acceso de
prueba gratuito hasta terminar la evaluación.

Los artículos elegibles de Builder Center pueden sumar 0,2 puntos cada uno,
hasta 0,6. El cierre publicado es el 14 de septiembre de 2026 a las 17:00 PDT
(20:00 Caracas). No confundir recomendaciones editoriales con obligaciones.

[Reglas oficiales, secciones 1, 4 y 6](https://agentsforhumans.devpost.com/rules).

## Qué se comprobó en esta sesión

- El checkout estaba limpio en `9ab4646` antes de añadir estas notas.
- Suite local: 2.106 pruebas pasaron y 66 se omitieron. Lint e higiene pasaron.
- GitHub reportó `CarSanoja/repaso` como privado en la consulta de esta sesión.
- El MP4 actual dura 280 segundos, tiene solo una pista de video y presenta
  diapositivas de conversaciones reconstruidas. No es la nueva demo propuesta.
- AWS devolvió seis pilas `repaso`: foundation, messaging y observability en
  CREATE_COMPLETE; api y agentcore en UPDATE_COMPLETE; guardrails en
  UPDATE_ROLLBACK_COMPLETE. Eso confirma existencia, no salud de extremo a
  extremo ni coincidencia entre código desplegado y checkout. La documentación
  antigua que dice que nunca hubo despliegue está desactualizada.
- Hay memoria de turnos, episodios de intentos, aprendizaje, decisiones,
  operaciones durables y recibos de entrega. Hay señales de dificultad grupal.
- Falta la experiencia completa de coordinador: permisos, revisión/aprobación y
  retorno de una intervención a las familias.

## Mensajes candidatos en inglés

Todos son propuestas de pitch, sujetos a lo que finalmente funcione en la demo.

**One line:** Repaso is the shared follow-up memory between learning at home and
the people helping a community learn.

**Product promise:** Repaso connects school material, practice at home, and the
next human intervention—so each decision has evidence and every next step can
be followed through.

**Opening:** A facilitator can support a whole group of children. Keeping track
of what each family tried, where a child got stuck, and what happens next is
another job. Repaso carries that follow-up between conversations.

**Live transition:** Watch this message become a recorded observation. Now watch
that observation change what happens next.

**Closing:** The conversation ends. The next step stays on record.

La duración propuesta será de 2–3 minutos si permite mostrar el ciclo completo.
No sacrificar la prueba de funcionamiento para cumplir una duración arbitraria.
El guion de pantallas y los requisitos técnicos están en
[live-memory-demo.md](live-memory-demo.md).
