from datetime import datetime

from app.config import Settings
from app.portal.automation import is_scheduled_working_day


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
