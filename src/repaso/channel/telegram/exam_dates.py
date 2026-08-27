import re
from datetime import date, datetime

DATE_FORMATS = ("%d-%m-%Y", "%Y-%m-%d")
DAY_MONTH = re.compile(r"^(\d{1,2})-(\d{1,2})$")


def parse_exam_date(token: str, today: date) -> date | None:
    normalized = token.strip().replace("/", "-")
    for pattern in DATE_FORMATS:
        try:
            return datetime.strptime(normalized, pattern).date()
        except ValueError:
            continue
    day_month = DAY_MONTH.match(normalized)
    if day_month is None:
        return None
    return _upcoming(int(day_month[1]), int(day_month[2]), today)


def split_exam_argument(argument: str, today: date) -> tuple[str, date] | None:
    tokens = argument.split()
    for index in reversed(range(len(tokens))):
        parsed = parse_exam_date(tokens[index], today)
        if parsed is not None:
            return " ".join(tokens[:index] + tokens[index + 1 :]), parsed
    return None


def _upcoming(day: int, month: int, today: date) -> date | None:
    for year in (today.year, today.year + 1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if candidate >= today:
            return candidate
    return None
