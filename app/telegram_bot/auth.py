"""Authorization helpers for Telegram command handlers."""

from __future__ import annotations

from telegram import Update

from app.config import Settings


def is_authorized(update: Update, settings: Settings) -> bool:
    """Verify the incoming update's chat matches the configured CHAT_ID."""
    if update.effective_chat is None:
        return False
    return str(update.effective_chat.id) == str(settings.chat_id)
