"""
Telegram command handlers.

See `.github/skills/telegram-command/SKILL.md` for registration and reply
formatting conventions followed here.
"""

from __future__ import annotations

import functools
import os
from datetime import datetime
from typing import Awaitable, Callable
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from app.config import get_settings
from app.logging_config import get_logger
from app.portal.automation import is_scheduled_working_day, perform_action
from app.telegram_bot.auth import is_authorized

logger = get_logger()

HandlerFunc = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]


def authorized_only(handler: HandlerFunc) -> HandlerFunc:
    """Decorator: reject the update with '🚫 Unauthorized.' unless it's from CHAT_ID."""

    @functools.wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        settings = get_settings()
        if not is_authorized(update, settings):
            await update.message.reply_text("🚫 Unauthorized.")
            return
        await handler(update, context)

    return wrapper


@authorized_only
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 *Work Check-in Bot*\n\n"
        "Available commands:\n"
        "/checkin — Perform check-in now\n"
        "/checkout — Perform check-out now\n"
        "/status — Show scheduler & bot status\n\n"
        "Automated check-in runs at 08:30, check-out at 17:30 on working days.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def _run_action_and_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str) -> None:
    settings = get_settings()
    chat_id = update.effective_chat.id
    label = "Check-in" if action == "checkin" else "Check-out"

    await context.bot.send_message(chat_id=chat_id, text=f"🚀 Starting {label.lower()}...")

    try:
        success, message = await perform_action(action, settings)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unhandled error running %s", action)
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Unexpected error: {exc}")
        return

    await context.bot.send_message(chat_id=chat_id, text=message)

    if success and os.path.exists(settings.screenshot_path):
        try:
            with open(settings.screenshot_path, "rb") as photo:
                await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=f"{label} proof screenshot")
        except Exception:
            logger.exception("Failed to send screenshot")
            await context.bot.send_message(chat_id=chat_id, text="⚠️ Action succeeded but failed to send screenshot.")


@authorized_only
async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _run_action_and_reply(update, context, "checkin")


@authorized_only
async def checkout_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _run_action_and_reply(update, context, "checkout")


@authorized_only
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        settings = get_settings()
        now = datetime.now(ZoneInfo(settings.timezone))
        working_today = "✅ Yes" if is_scheduled_working_day(settings, now) else "❌ No (weekend)"

        scheduler: AsyncIOScheduler | None = context.application.bot_data.get("scheduler")
        jobs_text = "N/A"
        if scheduler:
            jobs = scheduler.get_jobs()
            jobs_text = (
                "\n".join(f"• {job.name}: next run at {job.next_run_time}" for job in jobs) or "No scheduled jobs."
            )

        await update.message.reply_text(
            f"📊 *Bot Status*\n\n"
            f"Current time ({settings.timezone}): `{now.strftime('%Y-%m-%d %H:%M:%S')}`\n"
            f"Working day today: {working_today}\n\n"
            f"*Scheduled Jobs:*\n{jobs_text}",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as exc:  # noqa: BLE001 - never fail silently on a user command
        logger.exception("Failed to build /status reply")
        await update.message.reply_text(f"❌ Failed to retrieve status: {exc}")


def register_handlers(application: Application) -> None:
    """Register all command handlers. Call once when building the Application."""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("checkin", checkin_command))
    application.add_handler(CommandHandler("checkout", checkout_command))
    application.add_handler(CommandHandler("status", status_command))
