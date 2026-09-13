MESSAGES = {
    "practice_paused_today": (
        "Practice is paused for the rest of today: the daily service limit was "
        "reached. Nothing you sent was lost, and tomorrow picks up where you left "
        "off."
    ),
    "model_waiting": (
        "The AI service is temporarily at capacity. Your pending work is saved; you "
        "do not need to repeat your answer. Practice will continue when service is "
        "available. "
    ),
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
        "also keep names and personal details out of the uploaded pages.\n"
        "3. I store only what's needed: the alias, the grade, the school and section, the "
        "practice time, any exam dates you tell me, the material you send and the practice "
        "answers. /forget erases active data. Operational logs remain "
        "for up to 7 days and backups for up to 35 days; manage chat history in Telegram.\n"
        "4. This project is open source, but your data is not: nothing you send is "
        "published. Telegram and AWS process data to provide the service.\n"
        "Do you accept?"
    ),
    "consent_accept": "I accept",
    "consent_declined": "Understood. If you change your mind, type /start anytime.",
    "ask_alias": "What alias should we use for the student? (e.g. Leo, Star, Champ)",
    "alias_warning": "That looks like a real name. Better use a nickname only you know.",
    "ask_grade": "This pilot covers fourth-grade math. Enter 4 to continue.",
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
    "session_complete": (
        "Today's practice complete! Correct answers in a row: {streak}. See you tomorrow."
    ),
    "session_complete_fresh": (
        "Today's practice complete! What was hard today is exactly what we go over next. "
        "See you tomorrow."
    ),
    "material_received": "Received ✅ Preparing the material.",
    "material_ready": "Material ready: I prepared {item_count} exercises on {competencies}.",
    "material_unmatched": (
        "I couldn't place this page in the grade {grade} math syllabus I work from. It "
        "may be from another subject, another grade, or a topic I don't carry yet. If "
        "it is grade {grade} math and I got it wrong, resend it with a short note about "
        "the topic."
    ),
    "material_held": (
        "I set this page aside instead of practising from it: something in the text "
        "did not pass my safety check, so I won't build exercises from it. If it is a "
        "school worksheet, send me another photo of the same page."
    ),
    "material_interrupted": (
        "I stopped part way through this page: a step on my side did not finish. It is "
        "not your photo, and I haven't lost anything you sent. Send it again in a "
        "little while and I'll pick it up from there."
    ),
    "material_thin": (
        "This tells me the topic but not how the class works it. Could you send a "
        "photo of a solved exercise from the notebook?"
    ),
    "material_unreadable": (
        "I couldn't read the text on this page. The image may be dark or shaken, or "
        "the sheet may be blank. Could you send it again, straight on and with good "
        "light?"
    ),
    "material_unusable": (
        "I went through it and the questions it produced are not ones I would stand "
        "behind, so I'd rather send nothing than send something wrong. Could you send "
        "another photo, or the notebook page where the topic is worked out?"
    ),
    "rephoto_request": (
        "I didn't read this photo confidently enough to avoid guessing. It may be "
        "shaken or short of light. Can you retake it? If possible, send it as a file "
        "to keep the quality."
    ),
    "media_unreadable": (
        "That file didn't reach me, and I won't guess what I can't read. Can you send "
        "it again?"
    ),
    "quarantine_prompt": (
        'I need your eyes: {alias} answered "{answer}" and I\'m not sure how to grade '
        "it. Should it count as correct?"
    ),
    "quarantine_approve": "It's right",
    "quarantine_reject": "It's wrong",
    "quarantine_ack_approved": (
        "Thank you. I am counting it as right and it already adds to this week's progress."
    ),
    "quarantine_ack_rejected": (
        "Thank you. I record it as incorrect and use that result to adjust practice."
    ),
    "struggle_summary": (
        "{alias} has been struggling with {competency} for several days. Here is the "
        "evidence: {evidence}. What do you prefer?"
    ),
    "option_guided_session": "A guided 10-min session together tonight (I'll prepare it)",
    "option_teacher_note": "A note for the teacher (already drafted, you decide to send it)",
    "option_reduce_load": "One question per practice for seven days",
    "engagement_alert": (
        "{alias} hasn't practiced in {days} school days. Should we reduce the load or change "
        "the time? /schedule changes the hour, /pause stops without erasing anything."
    ),
    "cohort_note_intro": (
        "Heads up: {count} families in {section} are struggling with {competency} this "
        "week. I drafted a note for the teacher in case you want to share it:"
    ),
    "weekly_digest": (
        "{alias}'s weekly summary: {sessions} practices, {accuracy}% correct, "
        "{streak} correct-answer streak. Mastery by topic: {mastery_map}"
    ),
    "exam_ack": "Noted: {competency} exam on {date}. Adjusting the review plan.",
    "exam_ask_date": (
        "Happy to note it, but I'm missing the day. When is it? For example: 12/09 or 12-09-2026."
    ),
    "escalation_ack": ("Done: {option}."),
    "mastery_summary": "{mastered} mastered · {developing} on track · {struggling} tricky",
    "paused": "Paused. Nothing is erased; /resume picks up whenever you want.",
    "resumed": "Back! Tomorrow at {time} the next practice arrives.",
    "forget_confirm": (
        "This erases EVERYTHING: alias, material, history and statistics. It cannot be "
        "undone. Are you sure?"
    ),
    "forget_done": (
        "Profile, material, answers and alarms erased from the active service. Backups "
        "expire within 35 days and technical logs within seven days."
    ),
    "forget_yes": "Yes, erase everything",
    "forget_no": "No, keep it",
    "consent_decline": "I do not accept",
    "forget_keep": "Nothing was erased.",
    "help": (
        "/session practises a little more now\n/topic <topic> practises one topic\n"
        "/done closes the practice\n"
        "/schedule changes the practice time\n/exam registers an exam date\n"
        "/pause and /resume stop and restart\n/status shows progress\n"
        "/language switches language\n/forget erases all data"
    ),
    "unknown_chat": (
        "Hi, I'm Repaso. For now I only work with pilot families. If you have an "
        "invite code, send it to get started."
    ),
    "enrollment_closed": (
        "Hi, I'm Repaso. The pilot is not taking new families right now. Ask whoever "
        "invited you to write when a place opens up."
    ),
    "unknown_command": "I don't know that command. /help shows what I can do.",
    "status_line": "{alias}: {sessions} practices, mastery {mastery_map}, streak {streak}.",
    "supported_material": (
        "This pilot supports fourth-grade math: printed-text photos and single-page PDFs "
        "(up to 10 MB). Voice and handwriting are not available yet."
    ),
    "quarantine_unsure": "Not sure yet",
    "quarantine_deferred": (
        "The answer stays pending and does not change progress. You can review it with "
        "the teacher and return to these buttons."
    ),
    "study_open": (
        "Let's work on {topic}. I have {count} questions saved on it. "
        "Answer them together, no rush."
    ),
    "study_open_any": (
        "Let's do a short review. I have {count} questions saved. "
        "Answer them together, no rush."
    ),
    "study_question": "Question {asked} of {total}:",
    "study_right": "That's right! {rationale}",
    "study_wrong": "Not yet. The answer was: {answer}. {rationale}",
    "study_thin": (
        "On {topic} I only have {count} for now. We'll practise with those. Send me a "
        "photo of that page from the notebook and I'll prepare more for next time."
    ),
    "study_thin_any": (
        "For now I only have {count} saved questions. We'll practise with those. Send me "
        "a photo of the page you are on and I'll prepare more."
    ),
    "study_empty": (
        "I don't have any questions on {topic} yet. Send me a photo of that page from the "
        "notebook and I'll build the practice for it."
    ),
    "study_empty_any": (
        "I have no saved questions to practise right now. Send me a photo of the page you "
        "are on and I'll build the practice."
    ),
    "study_topic_unknown": (
        "I can't place that topic in the grade {grade} maths syllabus I work with. Try "
        "other words for it, or send me a photo of the page."
    ),
    "study_day_done": (
        "That's enough practice for today, and resting is part of learning too. "
        "Tomorrow we pick up what was hard today."
    ),
    "study_done": (
        "That's the end of this practice: {correct} of {answered}. What was hard today is "
        "exactly what we'll review."
    ),
    "study_done_time": (
        "We've been at it {minutes} minutes, so we'll stop here: {correct} of {answered}. "
        "A short spell every day beats one long one."
    ),
    "study_done_day": (
        "That closes today: {correct} of {answered}. We'll carry on tomorrow."
    ),
    "study_done_enough": (
        "These last ones are hard going, and pushing on tires more than it teaches. Let's "
        "stop here today: {correct} of {answered}. We'll review this topic calmly tomorrow."
    ),
    "study_done_bank": (
        "I've run out of the questions I had saved: {correct} of {answered}."
    ),
    "study_paused": "Practice paused. Write /session when you want to carry on.",
    "study_resumed": "Picking up where you left off.",
    "study_one_child": (
        "In this chat I follow a single student for now, so I don't know whose practice "
        "this would be."
    ),
    "study_stale_button": (
        "That question belonged to a practice we already closed. Write /session for "
        "another round."
    ),
    "study_none_open": (
        "There is no practice open right now. Write /session when you want one."
    ),
    "study_ask_topic": (
        "Which topic? For example: /topic equivalent fractions."
    ),
}
