from datetime import UTC, date, datetime, timedelta

from repaso.core.harness.practice_budget import (
    CONSECUTIVE_WRONG_STOP,
    DAILY_ITEM_ALLOWANCE,
    DAILY_ITEM_LIMIT,
    IDLE_MINUTES,
)
from repaso.core.harness.study_session import (
    budget_for,
    close_if_spent,
    is_expired,
    may,
    minutes_elapsed,
    open_session,
    questions_left,
    record_answer,
    record_served,
    stop_reason,
    transition,
)
from repaso.schemas.study_session import (
    Actor,
    CloseReason,
    StudyBudget,
    StudySessionStatus,
)

NOW = datetime(2026, 9, 14, 19, 0, tzinfo=UTC)
TODAY = date(2026, 9, 14)


def make_session(served_today: int = 0, **overrides):
    session = open_session(
        "sess-1", "f1", "s1", NOW, TODAY, budget_for(served_today), **overrides
    )
    return session


def start(session, now=NOW):
    return transition(session, StudySessionStatus.ACTIVE, Actor.FAMILY, now)


def test_a_session_opens_proposed_and_only_the_family_starts_it():
    session = make_session()
    assert session.status is StudySessionStatus.PROPOSED
    assert session.opened_by is Actor.FAMILY
    assert not may(session, StudySessionStatus.ACTIVE, Actor.SYSTEM)
    assert start(session).status is StudySessionStatus.ACTIVE


def test_only_the_family_resumes_a_paused_session():
    paused = transition(start(make_session()), StudySessionStatus.PAUSED, Actor.SYSTEM, NOW)
    assert paused.status is StudySessionStatus.PAUSED
    assert transition(paused, StudySessionStatus.ACTIVE, Actor.SYSTEM, NOW) is None
    assert transition(paused, StudySessionStatus.ACTIVE, Actor.FAMILY, NOW).status is (
        StudySessionStatus.ACTIVE
    )


def test_a_closed_session_never_moves_again():
    closed = transition(start(make_session()), StudySessionStatus.CLOSED, Actor.FAMILY, NOW)
    assert closed.closed_reason is CloseReason.FAMILY_CLOSED
    for target in StudySessionStatus:
        for actor in Actor:
            assert transition(closed, target, actor, NOW) is None


def test_only_the_system_abandons_and_it_says_the_session_expired():
    session = start(make_session())
    assert transition(session, StudySessionStatus.ABANDONED, Actor.FAMILY, NOW) is None
    abandoned = transition(session, StudySessionStatus.ABANDONED, Actor.SYSTEM, NOW)
    assert abandoned.status is StudySessionStatus.ABANDONED
    assert abandoned.closed_reason is CloseReason.EXPIRED


def test_the_budget_is_the_daily_capsule_and_the_day_holds_two_sittings():
    assert budget_for(0) == StudyBudget(questions=DAILY_ITEM_LIMIT, minutes=10)
    assert budget_for(DAILY_ITEM_LIMIT).questions == DAILY_ITEM_LIMIT
    assert budget_for(DAILY_ITEM_ALLOWANCE - 1).questions == 1
    assert budget_for(DAILY_ITEM_ALLOWANCE).questions == 0
    assert budget_for(DAILY_ITEM_ALLOWANCE + 5).questions == 0


def test_a_spent_budget_closes_the_session_instead_of_raising():
    session = start(make_session())
    for index in range(DAILY_ITEM_LIMIT):
        session = record_served(session, f"i{index}", NOW)
    assert questions_left(session) == 0
    closed = close_if_spent(session, NOW)
    assert closed.status is StudySessionStatus.CLOSED
    assert closed.closed_reason is CloseReason.QUESTIONS_SPENT


def test_the_minutes_run_out_even_when_questions_are_left():
    session = start(make_session())
    later = NOW + timedelta(minutes=session.budget.minutes)
    assert minutes_elapsed(session, later) == session.budget.minutes
    closed = close_if_spent(session, later)
    assert closed.closed_reason is CloseReason.MINUTES_SPENT


def test_three_wrong_in_a_row_stops_the_sitting_before_the_budget_does():
    session = start(make_session())
    for index in range(CONSECUTIVE_WRONG_STOP):
        session = record_answer(session, f"k{index}", False, NOW)
    assert session.progress.consecutive_wrong == CONSECUTIVE_WRONG_STOP
    assert stop_reason(session, NOW) is CloseReason.ENOUGH_FOR_TODAY
    assert close_if_spent(session, NOW).closed_reason is CloseReason.ENOUGH_FOR_TODAY


def test_one_right_answer_clears_the_run_of_wrong_ones():
    session = start(make_session())
    session = record_answer(session, "k1", False, NOW)
    session = record_answer(session, "k2", False, NOW)
    session = record_answer(session, "k3", True, NOW)
    assert session.progress.consecutive_wrong == 0
    assert session.progress.correct == 1
    assert session.progress.wrong == 2
    assert stop_reason(session, NOW) is None


def test_the_day_closes_the_sitting_when_the_child_already_practised_enough():
    session = start(make_session())
    assert stop_reason(session, NOW, served_today=DAILY_ITEM_ALLOWANCE) is CloseReason.DAY_SPENT


def test_an_answer_that_arrives_twice_is_counted_once():
    session = record_answer(start(make_session()), "sess-1:0", False, NOW)
    replayed = record_answer(session, "sess-1:0", False, NOW + timedelta(minutes=1))
    assert replayed.progress.answered_keys == ["sess-1:0"]
    assert replayed.progress.wrong == 1
    assert replayed.progress.consecutive_wrong == 1


def test_an_item_served_twice_spends_one_question():
    session = record_served(start(make_session()), "i1", NOW)
    assert questions_left(record_served(session, "i1", NOW)) == DAILY_ITEM_LIMIT - 1


def test_a_session_left_open_expires_and_a_session_from_yesterday_is_already_gone():
    session = start(make_session())
    assert not is_expired(session, NOW + timedelta(minutes=IDLE_MINUTES - 1), TODAY)
    assert is_expired(session, NOW + timedelta(minutes=IDLE_MINUTES), TODAY)
    assert is_expired(session, NOW, TODAY + timedelta(days=1))


def test_a_finished_session_cannot_expire():
    closed = transition(start(make_session()), StudySessionStatus.CLOSED, Actor.FAMILY, NOW)
    assert not is_expired(closed, NOW + timedelta(days=3), TODAY + timedelta(days=3))


def test_a_session_opened_with_nothing_left_in_the_day_is_already_spent():
    session = start(make_session(served_today=DAILY_ITEM_ALLOWANCE))
    assert session.budget.questions == 0
    assert close_if_spent(session, NOW).closed_reason is CloseReason.QUESTIONS_SPENT
