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
    "material_rejected": (
        "Ese material no parece de {subject}. Si crees que me equivoqué, reenvíalo con "
        "una nota corta del tema."
    ),
    "material_thin": (
        "Con esto solo conozco el tema, pero no cómo lo trabajan en clase. ¿Me mandas "
        "una foto de un ejercicio resuelto del cuaderno?"
    ),
    "material_unusable": (
        "Lo revisé y los ejercicios que salieron de ahí no los puedo dar por buenos, "
        "así que prefiero no mandar nada antes que mandar algo mal. ¿Me envías otra "
        "foto, o la página del cuaderno donde el tema esté resuelto?"
    ),
    "rephoto_request": (
        "La foto salió borrosa y no quiero inventar lo que no leo. ¿Puedes tomarla de "
        "nuevo con más luz? Si puedes, envíala como archivo para que no pierda calidad."
    ),
    "media_unreadable": (
        "Ese archivo no me llegó completo y no quiero inventar lo que no leo. ¿Me lo "
        "envías de nuevo?"
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
    "mastery_summary": "{mastered} dominados · {developing} en camino · {struggling} difíciles",
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
    "status_line": "{alias}: {sessions} prácticas, dominio {mastery_map}, racha {streak}.",
    "supported_material": (
        "En este piloto trabajamos matemática de cuarto grado con fotos de texto impreso "
        "y PDF de una página (hasta 10 MB). Voz y manuscritos todavía no están "
        "disponibles."
    ),
    "quarantine_unsure": "No sé todavía",
    "quarantine_deferred": (
        "La respuesta queda pendiente, sin cambiar el avance. Puedes revisarla con el "
        "docente y volver a estos botones."
    ),
}
