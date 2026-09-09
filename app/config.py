"""
Centralized configuration.

All environment variables are read exactly once, here, and exposed as a
typed, immutable `Settings` object via `get_settings()`. No other module
should call `os.getenv` directly — this keeps configuration discoverable,
testable (settings can be constructed directly in tests), and avoids
scattering `os.getenv(...)` calls throughout the codebase.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

REQUIRED_ENV_VARS: tuple[str, ...] = (
    "PORTAL_URL",
    "PORTAL_USER",
    "PORTAL_PASS",
    "TELEGRAM_BOT_TOKEN",
    "CHAT_ID",
)


@dataclass(frozen=True)
class Settings:
    """Immutable application configuration."""

    # Portal
    portal_url: str
    portal_check_url: str
    portal_user: str
    portal_pass: str

    # Telegram
    telegram_bot_token: str
    chat_id: str

    # Server
    port: int
    timezone: str

    # Automation tuning
    screenshot_path: str = "proof.png"
    login_timeout_ms: int = 30_000
    action_timeout_ms: int = 15_000
    min_delay_minutes: float = 1.0
    max_delay_minutes: float = 10.0

    # Scheduling: Monday=0 ... Sunday=6. Default working week Mon-Fri.
    working_days: frozenset[int] = field(default_factory=lambda: frozenset({0, 1, 2, 3, 4}))
    # Check-in fires at a random time in [window_start, deadline) every day;
    # the portal's own attendance table decides whether it's a working day.
    checkin_window_start_hour: int = 8
    checkin_window_start_minute: int = 0
    checkin_deadline_hour: int = 8
    checkin_deadline_minute: int = 30
    checkin_deadline_buffer_seconds: int = 30
    checkout_hour: int = 17
    checkout_minute: int = 30

    def missing_required(self) -> list[str]:
        """Return the list of required env var names that are unset/empty."""
        values = {
            "PORTAL_URL": self.portal_url,
            "PORTAL_USER": self.portal_user,
            "PORTAL_PASS": self.portal_pass,
            "TELEGRAM_BOT_TOKEN": self.telegram_bot_token,
            "CHAT_ID": self.chat_id,
        }
        return [name for name in REQUIRED_ENV_VARS if not values[name]]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Build (and cache) the Settings singleton from environment variables."""
    portal_url = os.getenv("PORTAL_URL", "")
    return Settings(
        portal_url=portal_url,
        # Page reached after login where the check-in/out button lives.
        # Falls back to PORTAL_URL if unset (e.g. login lands directly on it).
        portal_check_url=os.getenv("PORTAL_CHECK_URL", "") or portal_url,
        portal_user=os.getenv("PORTAL_USER", ""),
        portal_pass=os.getenv("PORTAL_PASS", ""),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        chat_id=os.getenv("CHAT_ID", ""),
        port=int(os.getenv("PORT", "10000")),
        timezone=os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh"),
        checkin_window_start_hour=int(os.getenv("CHECKIN_WINDOW_START_HOUR", "8")),
        checkin_window_start_minute=int(os.getenv("CHECKIN_WINDOW_START_MINUTE", "0")),
        checkin_deadline_hour=int(os.getenv("CHECKIN_DEADLINE_HOUR", "8")),
        checkin_deadline_minute=int(os.getenv("CHECKIN_DEADLINE_MINUTE", "30")),
        checkout_hour=int(os.getenv("CHECKOUT_HOUR", "17")),
        checkout_minute=int(os.getenv("CHECKOUT_MINUTE", "30")),
    )
