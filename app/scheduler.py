"""APScheduler wiring: automated daily check-in/check-out jobs."""

from __future__ import annotations

import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application

from app.config import Settings
from app.logging_config import get_logger
from app.portal.automation import is_scheduled_working_day, perform_action, random_delay

logger = get_logger()


async def scheduled_job(action: str, application: Application, settings: Settings) -> None:
    """Wraps `perform_action` for scheduler use: checks working day, adds jitter, notifies Telegram."""
    label = "Check-in" if action == "checkin" else "Check-out"

    if not settings.chat_id:
        logger.error("CHAT_ID not configured; skipping scheduled %s", action)
        return

    if not is_scheduled_working_day(settings):
        logger.info("Skipping scheduled %s: not a working day", action)
        return

    try:
        await application.bot.send_message(
            chat_id=settings.chat_id,
            text=f"⏳ Scheduled {label.lower()} triggered. Waiting random delay before proceeding...",
        )
        await random_delay(settings)

        success, message = await perform_action(action, settings)
        await application.bot.send_message(chat_id=settings.chat_id, text=message)

        if success and os.path.exists(settings.screenshot_path):
            with open(settings.screenshot_path, "rb") as photo:
                await application.bot.send_photo(
                    chat_id=settings.chat_id, photo=photo, caption=f"{label} proof screenshot"
                )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Scheduled %s failed", action)
        try:
            await application.bot.send_message(chat_id=settings.chat_id, text=f"❌ Scheduled {label.lower()} failed: {exc}")
        except Exception:
            logger.exception("Failed to notify Telegram about scheduled job failure")


def setup_scheduler(application: Application, settings: Settings) -> AsyncIOScheduler:
    """Create, register jobs on, and start the AsyncIOScheduler."""
    scheduler = AsyncIOScheduler(timezone=settings.timezone)

    scheduler.add_job(
        scheduled_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour=settings.checkin_hour,
        minute=settings.checkin_minute,
        args=["checkin", application, settings],
        name="Automated Check-in",
        id="checkin_job",
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        scheduled_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour=settings.checkout_hour,
        minute=settings.checkout_minute,
        args=["checkout", application, settings],
        name="Automated Check-out",
        id="checkout_job",
        misfire_grace_time=3600,
    )

    scheduler.start()
    logger.info("Scheduler started with jobs: %s", [job.id for job in scheduler.get_jobs()])
    return scheduler
