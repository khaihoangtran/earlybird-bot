# Work Check-in/Check-out Telegram Bot

An automated attendance bot that logs into your work portal using
[Playwright](https://playwright.dev/python/), performs check-in/check-out on
a schedule (or on demand via Telegram commands), and reports status +
screenshot proof back to you on Telegram. Designed to run as a **Render Web
Service**.

## Features
- `/checkin`, `/checkout` — trigger actions manually.
- `/status` — view current time, working-day status, and next scheduled runs.
- Automated daily check-in at **08:30** and check-out at **17:30**, every
  day of the week — the portal's own `UI_TAT_028` attendance table (not a
  Mon-Fri weekday check) decides whether today is actually a working day, so
  weekends marked as a compensation "Business Day" are still handled, while
  public holidays and approved leave requests are correctly skipped.
- Random 1–10 minute delay injected before each automated action to avoid
  suspiciously exact timestamps.
- Screenshot proof (`proof.png`) sent to Telegram after every action.
- Only responds to the Telegram user/chat ID configured in `CHAT_ID`.
- Flask `/health` endpoint on a daemon thread so Render's health checks pass.

## Project Structure
```
.
├── main.py                    # Thin entrypoint: wires config, server, scheduler, telegram bot
├── app/
│   ├── config.py               # Centralized Settings (reads all env vars once)
│   ├── logging_config.py       # Shared logging setup
│   ├── server.py                # Flask health-check app (/health, /)
│   ├── scheduler.py              # APScheduler jobs (automated check-in/out)
│   ├── portal/
│   │   └── automation.py          # Playwright login + punch-in/out automation
│   └── telegram_bot/
│       ├── auth.py                 # CHAT_ID authorization check
│       └── handlers.py             # /start, /checkin, /checkout, /status
├── tests/                        # pytest unit tests (config, working-day logic)
├── requirements.txt               # Runtime dependencies
├── requirements-dev.txt           # + pytest for local development
├── pyproject.toml                  # pytest/ruff/black configuration
├── .env.example                    # Environment variable template
├── Dockerfile                       # Render-ready container image
└── .github/
    ├── copilot-instructions.md
    └── skills/
        ├── portal-automation/SKILL.md
        └── telegram-command/SKILL.md
```

Each `app/` module has a single responsibility, making it easy to extend or
swap in isolation (e.g. add a new command in `telegram_bot/handlers.py`
without touching Playwright code, or change the portal's selectors in
`portal/automation.py` without touching Telegram/scheduling logic). All
configuration is centralized in `app/config.py` — no other module reads
`os.getenv` directly, which keeps behavior predictable and testable.

## 1. Local Development Setup

### Prerequisites
- Python 3.10+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- Your numeric Telegram chat ID (get it from [@userinfobot](https://t.me/userinfobot))

### Steps
```bash
# Clone and enter the repo
git clone <your-repo-url>
cd my-bot

# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Install Playwright's Chromium browser + OS deps
playwright install chromium --with-deps

# Configure environment variables
copy .env.example .env         # Windows
# cp .env.example .env         # macOS/Linux
# then edit .env with your real values
```

Edit `.env` with your portal URL/credentials, bot token, and chat ID:
```
PORTAL_URL=https://your-work-portal.example.com/login
PORTAL_CHECK_URL=https://your-work-portal.example.com/attendance
PORTAL_USER=your_portal_username
PORTAL_PASS=your_portal_password
TELEGRAM_BOT_TOKEN=123456789:ABCDefGhIJKlmNoPQRsTUVwxyZ
CHAT_ID=123456789
PORT=10000
TIMEZONE=Asia/Ho_Chi_Minh
```

Run the bot:
```bash
python main.py
```

Open `http://localhost:10000/health` in a browser to confirm the health
endpoint responds, and message your bot on Telegram with `/start`.

> ⚠️ **Important:** The default selectors in `app/portal/automation.py` are
> generic placeholders (`#username`, `button.webix_button`, etc.). Inspect
> your actual work portal's HTML and update these selectors — see
> `.github/skills/portal-automation/SKILL.md` for selector-priority guidance.

## Running Tests
This project uses `pytest` for unit tests covering configuration and
working-day scheduling logic (Playwright/Telegram network calls are not
exercised by these tests — they're fast, offline unit tests).

```bash
pip install -r requirements-dev.txt
pytest -v
```

Lint/format (optional, config lives in `pyproject.toml`):
```bash
pip install ruff black
ruff check .
black .
```

## 2. Deploying to Render

### Option A — Docker Web Service (recommended)
1. Push this repository to GitHub.
2. In the [Render Dashboard](https://dashboard.render.com/), click
   **New +** → **Web Service**.
3. Connect your GitHub repo. Render will detect the `Dockerfile`
   automatically — choose **Docker** as the environment.
4. Set the following **Environment Variables** in the Render dashboard:

   | Key | Value |
   |---|---|
   | `PORTAL_URL` | Your work portal login URL |
   | `PORTAL_CHECK_URL` | Page reached after login where the check-in/out button lives (optional; defaults to `PORTAL_URL`) |
   | `PORTAL_USER` | Your portal username |
   | `PORTAL_PASS` | Your portal password |
   | `TELEGRAM_BOT_TOKEN` | Token from @BotFather |
   | `CHAT_ID` | Your Telegram numeric chat ID |
   | `TIMEZONE` | e.g. `Asia/Ho_Chi_Minh` |
   | `PORT` | `10000` (Render also sets this automatically) |

5. Set the **Health Check Path** to `/health`.
6. Deploy. Render will build the Docker image (based on
   `mcr.microsoft.com/playwright/python:v1.45.0-jammy`, which already
   includes all browser binaries and OS dependencies) and start the service.

### Option B — Native Python Web Service
If you prefer not to use Docker:
1. **Build Command:** `pip install -r requirements.txt && playwright install --with-deps chromium`
2. **Start Command:** `python main.py`
3. Set the same environment variables as above.

> Render Web Services require binding to `$PORT` and responding to HTTP
> requests — this is why `main.py` runs a Flask server (with `/health`) on a
> background thread alongside the Telegram bot's polling loop.

### Keeping the Service Alive (Free Tier)
Render's free tier spins down web services after ~15 minutes of no HTTP
traffic. Since this bot relies on long-running Telegram polling and an
APScheduler that must fire at exact times (08:30/17:30), a sleeping service
will miss scheduled runs. Use a free external uptime monitor to periodically
ping `/health` and keep the service awake:

**Using UptimeRobot (free, recommended):**
1. Sign up at [uptimerobot.com](https://uptimerobot.com) (free plan).
2. Click **+ Add New Monitor**.
3. Monitor Type: **HTTP(s)**.
4. URL: `https://<your-render-app>.onrender.com/health`.
5. Monitoring Interval: **5 minutes** (well under Render's 15-min sleep window).
6. Save. UptimeRobot will now ping `/health` every 5 minutes, 24/7, keeping
   the service from spinning down.

Alternatives: [cron-job.org](https://cron-job.org) (free, supports 1-minute
intervals) or [Better Stack / Freshping](https://betterstack.com) offer
similar free uptime-ping monitors.

> For guaranteed reliability (no dependency on a third-party pinger), consider
> Render's paid "always-on" tier, or self-host on an always-free VM (e.g.
> [Oracle Cloud Always Free](https://www.oracle.com/cloud/free/)).

## Telegram Commands
| Command | Description |
|---|---|
| `/start` | Show welcome message and available commands |
| `/checkin` | Manually trigger check-in now |
| `/checkout` | Manually trigger check-out now |
| `/status` | Show current time, working-day status, and next scheduled job runs |

## Customizing Selectors
The Playwright selectors used in `app/portal/automation.py` are specific to
this portal's login form and its Webix "Punch In/Out" button. Update the
`USERNAME_SELECTOR`, `PASSWORD_SELECTOR`, `SUBMIT_SELECTOR`, and
`PUNCH_BUTTON_SELECTOR` constants at the top of that file to match your
portal's actual HTML (inspect via browser DevTools). See
`.github/skills/portal-automation/SKILL.md` for the selector-priority
strategy used throughout this project.

## How Working-Day Detection Works
The scheduler runs the check-in/check-out job **every day of the week**
(not just Mon-Fri) at 08:30/17:30. Before clicking the punch button,
`perform_action` calls `verify_portal_working_day()`, which reads today's row
directly from the portal's own `UI_TAT_028` attendance table:
- Working Holiday == `"Business Day"` and Leave Request != `"Yes"` → proceed.
- Otherwise (Weekend, a public holiday, a "Compensation Day" off, or an
  approved leave request) → skip.

This means weekends that the portal marks as a compensation "Business Day"
are still checked in/out correctly, which a plain Mon-Fri weekday check would
have missed. A `⏭️ Skipped ...` reply from `/checkin` or `/checkout` (or from
the scheduled job) is expected/normal behavior on non-working days, not an
error. The old Mon-Fri `is_scheduled_working_day()` heuristic is now only
used for the informational `/status` display and as a fallback when today's
row can't be found on the portal table (e.g. wrong month displayed).

Because that Webix grid virtualizes rows (only renders enough rows to fill
the viewport), the automation uses a tall browser viewport
(`height=2200` in `perform_action`) so the whole current month — including
today's row — is rendered before scraping. If your portal's calendar table
ever needs more rows than that (e.g. a very tall/dense layout), increase this
value. See `.github/skills/portal-automation/SKILL.md` for the column
selectors and date format this relies on.

## Security Notes
- The bot only responds to commands from the chat ID configured in `CHAT_ID`;
  all other users receive `🚫 Unauthorized.`
- Never commit your real `.env` file or `proof.png` screenshots — both should
  remain untracked (add to `.gitignore` if not already).
- Secrets are read exclusively from environment variables, never hardcoded.

## Troubleshooting
- **Bot doesn't respond:** Confirm `TELEGRAM_BOT_TOKEN` is correct and the
  service is running (check `/health`).
- **Login fails / timeout:** Update selectors in `_login()` to match your
  portal; increase `LOGIN_TIMEOUT_MS` if the portal is slow.
- **No screenshot received:** Check Render logs for exceptions during
  `perform_action`; ensure the `proof.png` write path is writable (it is, by
  default, in the container's working directory).
