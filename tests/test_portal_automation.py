from datetime import datetime

from app.config import Settings
from app.portal.automation import _find_today_status, _seconds_until_deadline, is_scheduled_working_day


def _make_settings(**overrides) -> Settings:
    defaults = dict(
        portal_url="https://portal.example.com/login",
        portal_check_url="https://portal.example.com/attendance",
        portal_user="user",
        portal_pass="pass",
        telegram_bot_token="token",
        chat_id="123",
        port=10000,
        timezone="UTC",
    )
    defaults.update(overrides)
    return Settings(**defaults)


def test_monday_is_a_working_day():
    settings = _make_settings()
    monday = datetime(2024, 1, 1)  # 2024-01-01 is a Monday
    assert is_scheduled_working_day(settings, monday) is True


def test_saturday_is_not_a_working_day():
    settings = _make_settings()
    saturday = datetime(2024, 1, 6)  # 2024-01-06 is a Saturday
    assert is_scheduled_working_day(settings, saturday) is False


def test_custom_working_days_are_respected():
    # A settings instance that only works Sundays.
    settings = _make_settings(working_days=frozenset({6}))
    sunday = datetime(2024, 1, 7)
    monday = datetime(2024, 1, 8)
    assert is_scheduled_working_day(settings, sunday) is True
    assert is_scheduled_working_day(settings, monday) is False


# --------------------------------------------------------------------------- #
# _find_today_status — pure row-matching logic scraped from UI_TAT_028
# --------------------------------------------------------------------------- #

DATES = ["Aug 24, 2026", "Aug 25, 2026", "Aug 26, 2026", "Aug 27, 2026", "Aug 28, 2026"]
WORKING_HOLIDAYS = ["Weekend", "Business Day", "Business Day", "Business Day", "Business Day"]
LEAVE_REQUESTS = ["", "", "", "Yes", ""]


def test_find_today_status_matches_business_day_row():
    status = _find_today_status(DATES, WORKING_HOLIDAYS, LEAVE_REQUESTS, "Aug 26, 2026")
    assert status == {"date": "Aug 26, 2026", "working_holiday": "Business Day", "leave_request": ""}


def test_find_today_status_matches_leave_request_row():
    status = _find_today_status(DATES, WORKING_HOLIDAYS, LEAVE_REQUESTS, "Aug 27, 2026")
    assert status == {"date": "Aug 27, 2026", "working_holiday": "Business Day", "leave_request": "Yes"}


def test_find_today_status_matches_weekend_row():
    status = _find_today_status(DATES, WORKING_HOLIDAYS, LEAVE_REQUESTS, "Aug 24, 2026")
    assert status["working_holiday"] == "Weekend"


def test_find_today_status_returns_none_when_date_not_found():
    assert _find_today_status(DATES, WORKING_HOLIDAYS, LEAVE_REQUESTS, "Sep 01, 2026") is None


# --------------------------------------------------------------------------- #
# _seconds_until_deadline — pure time-window math for the check-in deadline
# --------------------------------------------------------------------------- #


def test_seconds_until_deadline_returns_remaining_minus_buffer():
    settings = _make_settings()
    now = datetime(2026, 8, 27, 8, 0, 0)
    remaining = _seconds_until_deadline(settings, deadline_hour=8, deadline_minute=30, buffer_seconds=30, now=now)
    assert remaining == 30 * 60 - 30


def test_seconds_until_deadline_returns_zero_when_deadline_passed():
    settings = _make_settings()
    now = datetime(2026, 8, 27, 8, 45, 0)
    remaining = _seconds_until_deadline(settings, deadline_hour=8, deadline_minute=30, buffer_seconds=30, now=now)
    assert remaining == 0.0


def test_seconds_until_deadline_returns_zero_when_within_buffer():
    settings = _make_settings()
    now = datetime(2026, 8, 27, 8, 29, 45)  # 15s before deadline, buffer is 30s
    remaining = _seconds_until_deadline(settings, deadline_hour=8, deadline_minute=30, buffer_seconds=30, now=now)
    assert remaining == 0.0
