# Piloto de tres días: utilidad y atención del adulto

**Estado:** protocolo preparado; no se han observado participantes. Empezar solo cuando el recorrido desplegado funcione con material admitido, borrado y recuperación, y las familias tengan una invitación autorizada. Objetivo: observar 3–5 familias y un docente, sin convertir una simulación en evidencia de uso.

## Sesión inicial de 20 minutos

Explicar el alcance: matemática de cuarto grado, texto impreso o PDF de una página, resultados que pueden ser incorrectos, participación voluntaria y posibilidad de pausar/borrar. Pedir consentimiento del representante y asentimiento del niño con lenguaje comprensible. No solicitar nombres reales en los archivos de investigación. Usar códigos F01–F05; guardar contactos y consentimientos fuera del repositorio. Una autorización para usar el producto no implica permiso para publicar una cita, imagen o conversación.

Observar sin ayudar durante las primeras tareas: alta, envío de una hoja autorizada, recepción programada, tres respuestas y una decisión del adulto. Si hace falta intervenir, registrar el paso y el tiempo del operador. Mostrar cómo pausar y solicitar borrado. Parar la actividad ante malestar, una respuesta dañina o un fallo de aislamiento; resolver antes de continuar.

## Tres días y comparación

Para una tarea comparable, el adulto prepara manualmente una práctica breve a partir de una hoja. Cronometrar preparación, acompañamiento, revisión y corrección de errores por separado. En Repaso registrar las mismas categorías y toda ayuda del operador. Alternar el orden de la tarea manual/Repaso entre familias para reducir un sesgo sencillo de familiaridad. No prometer una comparación causal con tan pocos casos.

Durante tres días registrar oportunidades programadas, sesiones recibidas y completadas, preguntas respondidas, cuarentenas, decisiones terminadas, rechazos de material, abandonos y solicitudes de ayuda. Un envío planificado no cuenta como recibido. Si falta observación, dejar el valor en blanco: cero significa observado y nulo significa desconocido.

`observations.csv` tiene solo encabezados. Completar una fila por familia/día; `mode` debe ser `repaso` o `manual`, nunca `simulated`. No copiar respuestas infantiles ni chats. Para analizar: `python scripts/analyze_pilot.py private/pilot/observations.csv`. Publicar únicamente agregados revisados y autorizados.

## Preguntas al cerrar

Al adulto: «¿En qué momento necesitaste ayuda?», «¿Qué te hizo dudar de la evaluación?», «¿Qué trabajo te ahorró y qué trabajo añadió?», «¿Lo usarías mañana con otra hoja?». Al docente: revisar pertinencia de diez preguntas, claves, explicaciones y una nota; marcar cada error y si la nota propone una acción útil. Recoger dos observaciones de familias y una evaluación docente con autorización específica para citar, o parafrasearlas sin identificar.

## Resultado defendible

Informar familias invitadas/participantes, días observados, sesiones recibidas/programadas y completadas/recibidas. Mostrar la mediana y el rango de minutos activos del adulto, el tiempo del operador, incidencias y todos los abandonos. Comparar tareas solo en familias con ambas condiciones observadas. Una reducción de preparación o continuidad de tres días puede ser útil; estos datos no demuestran mejora de aprendizaje.
