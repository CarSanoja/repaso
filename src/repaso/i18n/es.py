MESSAGES = {
    "practice_paused_today": (
        "Por hoy la práctica queda en pausa: se alcanzó el límite diario de uso del "
        "servicio. No se perdió nada de lo que enviaron y mañana seguimos donde "
        "quedaron."
    ),
    "model_waiting": (
        "El servicio de IA está temporalmente sin capacidad. Guardé el trabajo "
        "pendiente; no hace falta repetir tu respuesta. La práctica continuará "
        "cuando vuelva a estar disponible. "
    ),
    "welcome": (
        "Hola, soy Repaso, el tutor de refuerzo de tu familia. Yo trabajo contigo, "
        "el representante: tú me mandas el material del colegio y yo armo una práctica "
        "corta cada día para tu hijo o hija. Para empezar necesito tu consentimiento."
    ),
    "consent": (
        "Antes de empezar, lo importante:\n"
        "1. La cuenta es tuya, del representante. Tu hijo o hija nunca usa Telegram: "
        "la práctica llega a este chat y ustedes la hacen juntos.\n"
        "2. Nunca me des el nombre real del estudiante. Usaremos un alias que tú elijas; "
        "evita también nombres o datos personales en las hojas.\n"
        "3. Guardo solo lo necesario: el alias, el grado, el colegio y la sección, la hora "
        "de práctica, las fechas de examen que me digas, el material que envíes y las "
        "respuestas de práctica. /forget borra los datos activos. Los registros operativos "
        "se conservan hasta 7 días y las copias de respaldo hasta 35 días; el historial "
        "del chat se gestiona en Telegram.\n"
        "4. Este proyecto es de código abierto, pero tus datos no: nada de lo que envíes "
        "se publica. Telegram y AWS procesan los datos para prestar el servicio.\n"
        "¿Aceptas estas condiciones?"
    ),
    "consent_accept": "Acepto",
    "consent_declined": "Entendido. Si cambias de opinión, escribe /start cuando quieras.",
    "ask_alias": "¿Qué alias usamos para el estudiante? (por ejemplo: Leo, Estrella, Campeón)",
    "alias_warning": ("Ese parece un nombre real. Mejor usa un apodo que solo ustedes conozcan."),
    "ask_grade": "Este piloto cubre matemática de cuarto grado. Escribe 4 para continuar.",
    "ask_section": (
        "¿Colegio, grado y sección? (por ejemplo: San José 4to B). Esto me deja avisarte "
        "si varias familias de la misma sección tropiezan con el mismo tema."
    ),
    "ask_schedule": "¿A qué hora quieres la práctica diaria? (por ejemplo: 7pm)",
    "ask_first_material": (
        "Listo. Mándame una foto de una hoja impresa o un PDF de una página y armo la "
        "primera práctica de {alias}."
    ),
    "enrollment_done": (
        "Todo listo para {alias}. Cada día a las {time} llega una práctica de 5 a 10 "
        "minutos a este chat. Solo te interrumpo aparte cuando haya una decisión que "
        "tomar. /help muestra los comandos."
    ),
    "capsule_header": "Práctica de hoy para {alias} — {competency}",
    "feedback_correct": "¡Correcto! {feedback}",
    "feedback_incorrect": "Todavía no. {feedback}",
    "session_complete": (
        "¡Práctica de hoy completa! Racha de aciertos seguidos: {streak}. Hasta mañana."
    ),
    "session_complete_fresh": (
        "¡Práctica de hoy completa! Lo que costó hoy es justo lo que vamos a repasar. "
        "Hasta mañana."
    ),
    "material_received": "Recibido ✅ Estoy preparando el material.",
    "material_ready": "Material listo: preparé {item_count} ejercicios sobre {competencies}.",
    "material_unmatched": (
        "No conseguí ubicar esta página en el temario de matemática de {grade}.º grado "
        "con el que trabajo. Puede ser de otra materia, de otro grado, o de un tema que "
        "todavía no tengo cargado. Si es matemática de {grade}.º y me equivoqué, "
        "reenvíala con una nota corta del tema."
    ),
    "material_held": (
        "Aparté esta página en vez de practicar con ella: algo del texto no pasó mi "
        "revisión de seguridad, así que no voy a armar ejercicios a partir de ahí. Si "
        "es una hoja del colegio, mándame otra foto de la misma página."
    ),
    "material_interrupted": (
        "Me quedé a medias con esta página: un paso de mi proceso no llegó a terminar. "
        "No es por la foto y no perdí nada de lo que enviaste. Vuelve a mandarla en un "
        "rato y sigo desde ahí."
    ),
    "material_thin": (
        "Con esto solo conozco el tema, pero no cómo lo trabajan en clase. ¿Me mandas "
        "una foto de un ejercicio resuelto del cuaderno?"
    ),
    "material_unreadable": (
        "No logré leer el texto de esta página. Puede que la imagen esté oscura o "
        "movida, o que la hoja venga en blanco. ¿Me la mandas otra vez, de frente y "
        "con buena luz?"
    ),
    "material_unusable": (
        "Lo revisé y los ejercicios que salieron de ahí no los puedo dar por buenos, "
        "así que prefiero no mandar nada antes que mandar algo mal. ¿Me envías otra "
        "foto, o la página del cuaderno donde el tema esté resuelto?"
    ),
    "rephoto_request": (
        "No leí esta foto con la seguridad que necesito para no inventar nada. Puede "
        "estar movida o con poca luz. ¿Puedes tomarla de nuevo? Si puedes, envíala "
        "como archivo para que no pierda calidad."
    ),
    "media_unreadable": (
        "Ese archivo no me llegó y no quiero inventar lo que no leo. ¿Me lo envías de "
        "nuevo?"
    ),
    "quarantine_prompt": (
        'Necesito tu ojo: {alias} respondió "{answer}" y no estoy seguro de cómo '
        "calificarla. ¿La das por buena?"
    ),
    "quarantine_approve": "Está bien",
    "quarantine_reject": "Está mal",
    "quarantine_ack_approved": (
        "Gracias. La cuento como correcta y ya suma al avance de esta semana."
    ),
    "quarantine_ack_rejected": (
        "Gracias. La registro como incorrecta y ajusto el repaso con ese resultado."
    ),
    "struggle_summary": (
        "{alias} lleva varios días tropezando con {competency}. Esta es la evidencia: "
        "{evidence}. ¿Qué prefieres?"
    ),
    "option_guided_session": "Sesión guiada de 10 min juntos esta noche (te la preparo)",
    "option_teacher_note": "Nota para la maestra (ya está redactada, tú decides enviarla)",
    "option_reduce_load": "Un ejercicio por práctica durante siete días",
    "engagement_alert": (
        "{alias} lleva {days} días de clase sin practicar. ¿Reducimos la carga o cambiamos el "
        "horario? /schedule cambia la hora, /pause detiene sin borrar nada."
    ),
    "cohort_note_intro": (
        "Aviso: {count} familias de {section} están tropezando con {competency} esta "
        "semana. Redacté una nota para la maestra por si quieres compartirla:"
    ),
    "weekly_digest": (
        "Resumen semanal de {alias}: {sessions} prácticas, {accuracy}% de aciertos, "
        "racha de {streak} días. Dominio por tema: {mastery_map}"
    ),
    "exam_ack": "Anotado: examen de {competency} el {date}. Ajusto el plan de repaso.",
    "exam_ask_date": (
        "Lo anoto con gusto, pero me falta el día. ¿Cuándo es? Por ejemplo: 12/09 o 12-09-2026."
    ),
    "escalation_ack": ("Listo: {option}."),
    "progress_summary": (
        "{holds} con evidencia de que le salen · {needs_help} donde necesita ayuda · "
        "{unknown} aún sin medir (pocas respuestas todavía)"
    ),
    "paused": "Pausado. Nada se borra; /resume retoma cuando quieran.",
    "resumed": "¡De vuelta! Mañana a las {time} llega la próxima práctica.",
    "forget_confirm": (
        "Esto borra TODO: alias, material, historial y estadísticas. No se puede deshacer. ¿Seguro?"
    ),
    "forget_done": (
        "Perfil, material, respuestas y alarmas borrados del servicio activo. Las copias "
        "de seguridad vencen en hasta 35 días y los registros técnicos en siete días."
    ),
    "forget_yes": "Sí, borrar todo",
    "forget_no": "No, conservar",
    "consent_decline": "No acepto",
    "forget_keep": "No borré nada.",
    "help": (
        "/sesion practica un rato más ahora\n/tema <tema> practica un tema\n"
        "/listo cierra la práctica\n"
        "/schedule cambia la hora de práctica\n/exam avisa una fecha de examen\n"
        "/pause y /resume detienen y retoman\n/status muestra el avance\n"
        "/language cambia el idioma\n/forget borra todos los datos"
    ),
    "unknown_chat": (
        "Hola, soy Repaso. Por ahora trabajo solo con familias del piloto. Si tienes un "
        "código de invitación, envíalo para empezar."
    ),
    "enrollment_closed": (
        "Hola, soy Repaso. Por ahora el piloto no recibe familias nuevas. Pídele a quien "
        "te invitó que te avise cuando se abra un cupo."
    ),
    "unknown_command": "No conozco ese comando. /help muestra lo que sé hacer.",
    "status_line": (
        "{alias}: {answers}, {correct}, en {topics}, en {days}.\n{progress_map}."
    ),
    "status_answers": "{count} preguntas respondidas",
    "status_answers_one": "1 pregunta respondida",
    "status_correct": "{count} correctas",
    "status_correct_one": "1 correcta",
    "status_topics": "{count} temas",
    "status_topics_one": "1 tema",
    "status_days": "{count} días de práctica registrados",
    "status_days_one": "1 día de práctica registrado",
    "supported_material": (
        "En este piloto trabajamos matemática de cuarto grado con fotos de texto impreso "
        "y PDF de una página (hasta 10 MB). Voz y manuscritos todavía no están "
        "disponibles."
    ),
    "turn_not_understood": ("No te entendí. ¿Me lo escribes otra vez con otras palabras?"),
    "turn_practice_done": (
        "La práctica de hoy ya está completa, así que esa no la cuento como respuesta. "
        "Mañana a las {time} llega la siguiente."
    ),
    "turn_practice_not_sent": (
        "Todavía no mandé la práctica de hoy; llega a las {time}. Si quieren adelantar, "
        "mándame una foto de la hoja del colegio y preparo los ejercicios."
    ),
    "turn_more_tomorrow": (
        "Por hoy son estas preguntas. Mañana a las {time} llega la práctica nueva. Si "
        "quieren seguir ahora, mándame una foto de otra página y armo ejercicios con ella."
    ),
    "turn_stop": ("Está bien, lo dejamos aquí por hoy. Lo que ya hicieron quedó guardado."),
    "turn_about_practice": (
        "Eso lo manejo con comandos: /status muestra el avance, /schedule cambia la hora, "
        "/exam anota una fecha de examen y /pause detiene sin borrar nada."
    ),
    "turn_off_task": ("Aquí sigo, para la práctica. Cuando quieran, seguimos con la pregunta."),
    "turn_explain_unavailable": (
        "Ahora mismo no logro explicarlo mejor. Prueba la pregunta otra vez y con lo que "
        "respondas te ayudo."
    ),
    "turn_blocked": (
        "Eso no lo puedo responder, pero seguimos: vuelve a la pregunta de la práctica."
    ),
    "quarantine_unsure": "No sé todavía",
    "quarantine_deferred": (
        "La respuesta queda pendiente, sin cambiar el avance. Puedes revisarla con el "
        "docente y volver a estos botones."
    ),
    "study_open": (
        "Vamos con {topic}. Tengo {count} preguntas guardadas de ese tema. "
        "Respondan juntos, sin apuro."
    ),
    "study_open_any": (
        "Vamos con un repaso corto. Tengo {count} preguntas guardadas. "
        "Respondan juntos, sin apuro."
    ),
    "study_question": "Pregunta {asked} de {total}:",
    "study_right": "¡Correcto! {rationale}",
    "study_wrong": "Todavía no. La respuesta era: {answer}. {rationale}",
    "study_thin": (
        "De {topic} solo tengo {count} por ahora. Practicamos con esas. Si me mandas una "
        "foto de esa página del cuaderno, preparo más para la próxima."
    ),
    "study_thin_any": (
        "Por ahora solo tengo {count} preguntas guardadas. Practicamos con esas. Si me "
        "mandas una foto de la página que están viendo, preparo más."
    ),
    "study_empty": (
        "Todavía no tengo preguntas de {topic}. Mándame una foto de esa página del "
        "cuaderno y armo la práctica de ese tema."
    ),
    "study_empty_any": (
        "Todavía no tengo preguntas guardadas para practicar ahora. Mándame una foto de "
        "la página que están viendo y armo la práctica."
    ),
    "study_topic_unknown": (
        "No ubico ese tema en el temario de matemática de {grade}.º grado con el que "
        "trabajo. Puedes decirme el tema con otras palabras, o mandarme una foto de la "
        "página."
    ),
    "study_day_done": (
        "Por hoy ya practicaron bastante, y descansar también es parte de aprender. "
        "Mañana seguimos con lo que costó hoy."
    ),
    "study_done": (
        "Terminamos esta práctica: {correct} de {answered}. Lo que costó hoy es justo lo "
        "que vamos a repasar."
    ),
    "study_done_time": (
        "Llevamos {minutes} minutos, así que lo dejamos aquí: {correct} de {answered}. "
        "Un rato corto todos los días rinde más que uno largo."
    ),
    "study_done_day": (
        "Con esta cerramos por hoy: {correct} de {answered}. Mañana seguimos."
    ),
    "study_done_enough": (
        "Estas últimas están costando, y seguir así cansa más de lo que enseña. Dejémoslo "
        "aquí por hoy: {correct} de {answered}. Este tema lo repasamos mañana con calma."
    ),
    "study_done_bank": (
        "Se me acabaron las preguntas que tenía guardadas: {correct} de {answered}."
    ),
    "study_paused": "Práctica en pausa. Cuando quieran seguir, escriban /sesion.",
    "study_resumed": "Seguimos donde quedaron.",
    "study_one_child": (
        "En este chat sigo a un solo estudiante por ahora, así que no sé de quién sería "
        "esta práctica."
    ),
    "study_stale_button": (
        "Esa pregunta era de una práctica que ya cerramos. Si quieren otra ronda, "
        "escriban /sesion."
    ),
    "study_none_open": (
        "No hay una práctica abierta ahora mismo. Escribe /sesion cuando quieran una."
    ),
    "study_ask_topic": (
        "¿De qué tema? Por ejemplo: /tema fracciones equivalentes."
    ),
    "study_open_one": (
        "Vamos con {topic}. Tengo 1 pregunta guardada de ese tema. "
        "Respóndanla juntos, sin apuro."
    ),
    "study_open_any_one": (
        "Vamos con un repaso corto. Tengo 1 pregunta guardada. "
        "Respóndanla juntos, sin apuro."
    ),
    "study_thin_one": (
        "De {topic} solo tengo 1 por ahora. Practicamos con esa. Si me mandas una "
        "foto de esa página del cuaderno, preparo más para la próxima."
    ),
    "study_thin_any_one": (
        "Por ahora solo tengo 1 pregunta guardada. Practicamos con esa. Si me "
        "mandas una foto de la página que están viendo, preparo más."
    ),
    "study_out_of_step": (
        "Esa respuesta salió antes de que te mandara esta pregunta, así que no la "
        "cuento aquí. Esta es la que toca ahora:"
    ),
    "study_not_an_answer": (
        "No supe cuál opción elegiste, así que no la cuento como respuesta. Toca una "
        "opción o escribe su número."
    ),
}
