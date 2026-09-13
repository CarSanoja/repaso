DAILY_ITEM_LIMIT = 3
SITTINGS_PER_DAY = 2
DAILY_ITEM_ALLOWANCE = DAILY_ITEM_LIMIT * SITTINGS_PER_DAY
SESSION_MINUTES = 10
CONSECUTIVE_WRONG_STOP = 3
IDLE_MINUTES = 60


def items_left_today(served_today: int) -> int:
    return max(0, DAILY_ITEM_ALLOWANCE - served_today)


def session_questions(served_today: int) -> int:
    return min(DAILY_ITEM_LIMIT, items_left_today(served_today))
