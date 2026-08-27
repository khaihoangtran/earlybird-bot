# Project Context

This is an automated attendance assistant written in Python and deployed on Render as a Web Service.

# Architecture

- `main.py` is a thin entrypoint only — it wires together `app/` package components (config, health server, scheduler, telegram bot) and starts them. Do not add business logic here.
- `app/config.py` is the single source of truth for environment variables via `get_settings()`. Never call `os.getenv()` outside this file — add new variables to `Settings` and `.env.example` instead.
- `app/portal/automation.py` contains all Playwright login/punch-in-out logic.
- `app/telegram_bot/` contains command handlers (`handlers.py`) and the CHAT_ID authorization check (`auth.py`).
- `app/scheduler.py` contains the APScheduler job definitions.
- `app/server.py` contains the Flask health-check app.
- `tests/` contains fast, offline pytest unit tests (config validation, working-day logic). Add tests here for any new pure-logic function.

# Technical Stack

- Playwright (Async API) for headless portal scraping & check-in automation.
- python-telegram-bot (v20+) for notification delivery and remote commands.
- Flask running on a background daemon thread to serve Render `/health` checks.
- APScheduler / asyncio loop for task scheduling and time randomization.

# Coding Guidelines

- Maintain strict async/await patterns for Playwright and Telegram calls.
- Never hardcode secrets or URLs; retrieve them via `app.config.get_settings()`.
- Always wrap browser operations in `try/except` blocks that send error alerts and DOM screenshots to Telegram upon failure.
- Validate that `update.effective_user.id` matches `CHAT_ID` before executing commands (use the `@authorized_only` decorator in `app/telegram_bot/handlers.py`).
- Keep each module single-purpose; when adding a feature, prefer extending the relevant existing module over adding logic to `main.py`.
