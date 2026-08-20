MESSAGES = {
    "welcome": (
        "Hi, I'm Repaso, your family's reinforcement tutor. I work with you, the "
        "parent: you send me whatever the school shares and I build a short daily "
        "practice for your child. First I need your consent."
    ),
    "consent": (
        "Before we start, what matters:\n"
        "1. The account is yours, the parent's. Your child never uses Telegram: "
        "practice arrives in this chat and you do it together.\n"
        "2. Never give me the student's real name. We'll use an alias you choose; "
        "real names never reach the system.\n"
        "3. I store only what's needed: the alias, the grade, the material you send "
        "and the practice answers. Erase everything anytime with /forget.\n"
        "4. This project is open source, but your data is not: nothing you send is "
        "published or shared.\n"
        "Do you accept?"
    ),
    "consent_accept": "I accept",
    "consent_declined": "Understood. If you change your mind, type /start anytime.",
    "ask_alias": "What alias should we use for the student? (e.g. Leo, Star, Champ)",
    "alias_warning": "That looks like a real name. Better use a nickname only you know.",
    "ask_grade": "What grade are they in? (1 to 12)",
    "ask_section": (
        "School, grade and section? (e.g. San Jose 4th B). This lets me tell you when "
        "several families in the same section struggle with the same topic."
    ),
    "ask_schedule": "What time do you want the daily practice? (e.g. 7pm)",
    "ask_first_material": (
        "Done. Send me a photo of the notebook, the worksheet or the weekly plan and "
        "I'll build {alias}'s first practice."
    ),
    "enrollment_done": (
        "{alias} is enrolled. Every day at {time} a 5-10 minute practice arrives in "
        "this chat. I only interrupt you separately when there is a decision to make. "
        "/help shows the commands."
    ),
    "capsule_header": "Today's practice for {alias} — {competency}",
    "feedback_correct": "Correct! {feedback}",
    "feedback_incorrect": "Not yet. {feedback}",
    "session_complete": "Today's practice complete! {streak}-day streak. See you tomorrow.",
    "material_received": "Received ✅ Preparing the material.",
    "material_ready": "Material ready: I prepared {item_count} exercises on {competencies}.",
    "material_rejected": (
        "That material doesn't look like {subject}. If I got it wrong, resend it with "
        "a short note about the topic."
    ),
    "material_thin": (
        "This tells me the topic but not how the class works it. Could you send a "
        "photo of a solved exercise from the notebook?"
    ),
    "rephoto_request": (
        "The photo came out blurry and I won't guess what I can't read. Can you retake "
        "it with more light? If possible, send it as a file to keep the quality."
    ),
    "quarantine_prompt": (
        "I need your eyes: {alias} answered \"{answer}\" and I'm not sure how to grade "
        "it. Should it count as correct?"
    ),
    "quarantine_approve": "It's right",
    "quarantine_reject": "It's wrong",
    "struggle_summary": (
        "{alias} has been struggling with {competency} for several days. Here is the "
        "evidence: {evidence}. What do you prefer?"
    ),
    "option_guided_session": "A guided 10-min session together tonight (I'll prepare it)",
    "option_teacher_note": "A note for the teacher (already drafted, you decide to send it)",
    "option_reduce_load": "Slow down and consolidate the previous topic",
    "engagement_alert": (
        "{alias} hasn't practiced in {days} days. Should we reduce the load or change "
        "the time? /schedule changes the hour, /pause stops without erasing anything."
    ),
    "cohort_note_intro": (
        "Heads up: {count} families in {section} are struggling with {competency} this "
        "week. I drafted a note for the teacher in case you want to share it:"
    ),
    "weekly_digest": (
        "{alias}'s weekly summary: {sessions} practices, {accuracy}% correct, "
        "{streak}-day streak. Mastery by topic: {mastery_map}"
    ),
    "exam_ack": "Noted: {competency} exam on {date}. Adjusting the review plan.",
    "paused": "Paused. Nothing is erased; /resume picks up whenever you want.",
    "resumed": "Back! Tomorrow at {time} the next practice arrives.",
    "forget_confirm": (
        "This erases EVERYTHING: alias, material, history and statistics. It cannot be "
        "undone. Are you sure?"
    ),
    "forget_done": "Everything erased. Thank you for trusting Repaso.",
    "forget_keep": "Nothing was erased.",
    "help": (
        "/schedule changes the practice time\n/exam registers an exam date\n"
        "/pause and /resume stop and restart\n/status shows progress\n"
        "/language switches language\n/forget erases all data"
    ),
    "unknown_chat": (
        "Hi, I'm Repaso. For now I only work with pilot families. If you have an "
        "invite code, send it to get started."
    ),
    "unknown_command": "I don't know that command. /help shows what I can do.",
    "status_line": "{alias}: {sessions} practices, mastery {mastery_map}, streak {streak}.",
}
