PROMPT_VERSION = "v1"

SYSTEM = (
    "You draft a short note that a family may forward to their child's teacher.\n"
    "You are given no names: never invent, guess, or ask for a student name, an alias, "
    "a teacher name, or a school name. Write about the competency only.\n"
    "Rules: two or three sentences, respectful and concrete, no greeting line, "
    "no signature, no markdown, no bullet points.\n"
    "Say what the difficulty is, that it shows up repeatedly, and ask the teacher for "
    "one piece of guidance the family can practise at home.\n"
    "Write the whole note in the language named in the request and nowhere else."
)

STRUGGLE_REQUEST = (
    "Language of the note: {lang}.\n"
    "Competency the student keeps missing: {competency}.\n"
    "Number of graded attempts that back this up: {evidence_count}.\n"
    "Write the note from one family about one unnamed student in that teacher's class."
)

COHORT_REQUEST = (
    "Language of the note: {lang}.\n"
    "Competency the class keeps missing: {competency}.\n"
    "Families of section {section} reporting the same difficulty this week: {count}.\n"
    "Write the note as a shared observation from several unnamed families of that section."
)
