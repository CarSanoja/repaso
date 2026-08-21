MESSAGES = {
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
        "los nombres reales jamás llegan al sistema.\n"
        "3. Guardo solo lo necesario: el alias, el grado, el material que envíes y las "
        "respuestas de práctica. Puedes borrarlo todo cuando quieras con /forget.\n"
        "4. Este proyecto es de código abierto, pero tus datos no: nada de lo que envíes "
        "se publica ni se comparte.\n"
        "¿Aceptas estas condiciones?"
    ),
    "consent_accept": "Acepto",
    "consent_declined": "Entendido. Si cambias de opinión, escribe /start cuando quieras.",
    "ask_alias": "¿Qué alias usamos para el estudiante? (por ejemplo: Leo, Estrella, Campeón)",
    "alias_warning": (
        "Ese parece un nombre real. Mejor usa un apodo que solo ustedes conozcan."
    ),
    "ask_grade": "¿En qué grado está? (1 a 12)",
    "ask_section": (
        "¿Colegio, grado y sección? (por ejemplo: San José 4to B). Esto me deja avisarte "
        "si varias familias de la misma sección tropiezan con el mismo tema."
    ),
    "ask_schedule": "¿A qué hora quieres la práctica diaria? (por ejemplo: 7pm)",
    "ask_first_material": (
        "Listo. Mándame una foto del cuaderno, la guía o el plan de la semana y armo la "
        "primera práctica de {alias}."
    ),
    "enrollment_done": (
        "{alias} queda inscrito. Cada día a las {time} llega una práctica de 5 a 10 "
        "minutos a este chat. Solo te interrumpo aparte cuando haya una decisión que "
        "tomar. /help muestra los comandos."
    ),
    "capsule_header": "Práctica de hoy para {alias} — {competency}",
    "feedback_correct": "¡Correcto! {feedback}",
    "feedback_incorrect": "Todavía no. {feedback}",
    "session_complete": "¡Práctica de hoy completa! Racha de {streak} días. Hasta mañana.",
    "material_received": "Recibido ✅ Estoy preparando el material.",
    "material_ready": "Material listo: preparé {item_count} ejercicios sobre {competencies}.",
    "material_rejected": (
        "Ese material no parece de {subject}. Si crees que me equivoqué, reenvíalo con "
        "una nota corta del tema."
    ),
    "material_thin": (
        "Con esto solo conozco el tema, pero no cómo lo trabajan en clase. ¿Me mandas "
        "una foto de un ejercicio resuelto del cuaderno?"
    ),
    "rephoto_request": (
        "La foto salió borrosa y no quiero inventar lo que no leo. ¿Puedes tomarla de "
        "nuevo con más luz? Si puedes, envíala como archivo para que no pierda calidad."
    ),
    "quarantine_prompt": (
        "Necesito tu ojo: {alias} respondió \"{answer}\" y no estoy seguro de cómo "
        "calificarla. ¿La das por buena?"
    ),
    "quarantine_approve": "Está bien",
    "quarantine_reject": "Está mal",
    "struggle_summary": (
        "{alias} lleva varios días tropezando con {competency}. Esta es la evidencia: "
        "{evidence}. ¿Qué prefieres?"
    ),
    "option_guided_session": "Sesión guiada de 10 min juntos esta noche (te la preparo)",
    "option_teacher_note": "Nota para la maestra (ya está redactada, tú decides enviarla)",
    "option_reduce_load": "Bajar el ritmo y consolidar el tema anterior",
    "engagement_alert": (
        "{alias} lleva {days} días sin practicar. ¿Reducimos la carga o cambiamos el "
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
    "paused": "Pausado. Nada se borra; /resume retoma cuando quieran.",
    "resumed": "¡De vuelta! Mañana a las {time} llega la próxima práctica.",
    "forget_confirm": (
        "Esto borra TODO: alias, material, historial y estadísticas. No se puede "
        "deshacer. ¿Seguro?"
    ),
    "forget_done": "Todo borrado. Gracias por confiar en Repaso.",
    "forget_keep": "No borré nada.",
    "help": (
        "/schedule cambia la hora de práctica\n/exam avisa una fecha de examen\n"
        "/pause y /resume detienen y retoman\n/status muestra el avance\n"
        "/language cambia el idioma\n/forget borra todos los datos"
    ),
    "unknown_chat": (
        "Hola, soy Repaso. Por ahora trabajo solo con familias del piloto. Si tienes un "
        "código de invitación, envíalo para empezar."
    ),
    "unknown_command": "No conozco ese comando. /help muestra lo que sé hacer.",
    "status_line": "{alias}: {sessions} prácticas, dominio {mastery_map}, racha {streak}.",
}
