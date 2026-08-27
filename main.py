"""
Automated Work Check-in/Check-out Telegram Bot — entrypoint.

Runs as a Render Web Service:
- A Flask app serves a `/health` endpoint on a daemon thread so Render's
  health checks pass (Render requires web services to bind to $PORT).
- A python-telegram-bot Application handles interactive commands.
- APScheduler (AsyncIOScheduler) triggers automated daily check-in/out.
- Playwright (async) drives the actual browser automation against the
  work portal.

This module is intentionally thin: it only wires together the `app`
package's components (config, server, scheduler, telegram_bot). Business
logic lives in `app/`; see that package for implementation details.
"""

from __future__ import annotations

import threading

from telegram import Update
from telegram.ext import Application

from app.config import get_settings
from app.logging_config import setup_logging
from app.scheduler import setup_scheduler
from app.server import run_health_server
from app.telegram_bot.handlers import register_handlers

logger = setup_logging()


async def _post_init(application: Application) -> None:
    """Runs once the Application is initialized; starts the scheduler and pings Telegram."""
    settings = get_settings()
    scheduler = setup_scheduler(application, settings)
    application.bot_data["scheduler"] = scheduler

    if settings.chat_id:
        try:
            await application.bot.send_message(chat_id=settings.chat_id, text="🤖 Check-in bot started and ready.")
        except Exception:
            logger.exception("Failed to send startup message to Telegram")


def main() -> None:
    settings = get_settings()

    missing = settings.missing_required()
    if missing:
        logger.warning(
            "Missing required environment variables: %s. "
            "The bot will start but automation will fail until these are set.",
            ", ".join(missing),
        )

    if not settings.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN is not set. Cannot start Telegram bot.")
        raise SystemExit(1)

    # Start Flask health-check server on a daemon thread.
    flask_thread = threading.Thread(target=run_health_server, args=(settings.port,), daemon=True)
    flask_thread.start()
    logger.info("Flask health-check server started on port %s", settings.port)

    application = Application.builder().token(settings.telegram_bot_token).post_init(_post_init).build()
    register_handlers(application)

    logger.info("Starting Telegram bot polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES, close_loop=False)


if __name__ == "__main__":
    main()
