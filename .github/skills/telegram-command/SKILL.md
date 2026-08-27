---
name: telegram-command
description: Guidelines for adding new slash commands, inline buttons, or interactive flows to the python-telegram-bot instance.
---

# Command Handler Conventions

1. **Immediate Feedback:** Send an initial status message (e.g., _"Checking schedule..."_) before launching heavy Playwright browser instances.
2. **Authentication Gatekeeper:** Wrap handler logic with an authorization check against `os.getenv("CHAT_ID")`.
3. **Response Formatting:** Use Markdown formatting for status messages and attach proof images via `bot.send_photo()` when available.
4. **Registration:** Every new `/command` function must be registered with `application.add_handler(CommandHandler("name", callback))` inside `main.py`.
