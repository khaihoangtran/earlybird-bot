"""
Playwright automation: login, working-day checks, and the punch in/out action.

See `.github/skills/portal-automation/SKILL.md` for the selector-priority
strategy and visual-proof requirements this module follows.
"""

from __future__ import annotations

import asyncio
import random
from datetime import datetime
from zoneinfo import ZoneInfo

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError, async_playwright

from app.config import Settings
from app.logging_config import get_logger

logger = get_logger()

# NOTE: Update these selectors to match your actual portal's login form.
USERNAME_SELECTOR = "#username, input[name='username'], input[type='text']"
PASSWORD_SELECTOR = "#password, input[name='password'], input[type='password']"
SUBMIT_SELECTOR = "button[type='submit'], #submit-btn"

# This portal uses a single "Punch In/Out" Webix button for both check-in
# and check-out — the portal itself toggles state based on current
# attendance status, so the same selector is used regardless of action.
PUNCH_BUTTON_SELECTOR = "button.webix_button:has-text('Punch In/Out')"

# UI_TAT_028 attendance table columns (see UI_TAT_028_example.html): each
# column is rendered as its own `div[column="N"]` containing one
# `div[role="gridcell"]` per row of the current month, in the same row order
# across columns (column 0 = Date, 3 = Working Holiday, 4 = Leave Request).
DATE_COLUMN_SELECTOR = 'div[column="0"] div[role="gridcell"]'
WORKING_HOLIDAY_COLUMN_SELECTOR = 'div[column="3"] div[role="gridcell"]'
LEAVE_REQUEST_COLUMN_SELECTOR = 'div[column="4"] div[role="gridcell"]'

# Cell text values as rendered by the portal.
BUSINESS_DAY_LABEL = "Business Day"
LEAVE_REQUEST_YES = "Yes"

# Portal's Date column format, e.g. "Aug 27, 2026".
PORTAL_DATE_FORMAT = "%b %d, %Y"


def is_scheduled_working_day(settings: Settings, reference: datetime | None = None) -> bool:
    """
    Return True if `reference` (default: now, in `settings.timezone`) falls on
    the standard Mon-Fri work week.

    This is a cheap, offline heuristic used to avoid launching a browser at
    all on weekends (see `setup_scheduler`). It does NOT account for public
    holidays or approved leave requests — use `verify_portal_working_day` for
    the authoritative check against the portal's own attendance table before
    actually punching in/out.
    """
    now = reference or datetime.now(ZoneInfo(settings.timezone))
    return now.weekday() in settings.working_days


def _find_today_status(
    dates: list[str],
    working_holidays: list[str],
    leave_requests: list[str],
    today_str: str,
) -> dict[str, str] | None:
    """
    Pure helper (no Playwright/IO): locate `today_str` in `dates` and return
    the corresponding Working Holiday / Leave Request cell text for that row,
    or None if today's date isn't present in the scraped table (e.g. the
    portal is showing a different month).
    """
    try:
        idx = dates.index(today_str)
    except ValueError:
        return None

    return {
        "date": dates[idx],
        "working_holiday": working_holidays[idx] if idx < len(working_holidays) else "",
        "leave_request": leave_requests[idx] if idx < len(leave_requests) else "",
    }


async def get_portal_day_status(page: Page, settings: Settings) -> dict[str, str] | None:
    """
    Scrape the UI_TAT_028 attendance table (must already be loaded in `page`)
    for today's row, returning its Date/Working Holiday/Leave Request values,
    or None if today's date isn't found in the currently displayed month.
    """
    dates = await page.eval_on_selector_all(DATE_COLUMN_SELECTOR, "els => els.map(e => e.textContent.trim())")
    working_holidays = await page.eval_on_selector_all(
        WORKING_HOLIDAY_COLUMN_SELECTOR, "els => els.map(e => e.textContent.trim())"
    )
    leave_requests = await page.eval_on_selector_all(
        LEAVE_REQUEST_COLUMN_SELECTOR, "els => els.map(e => e.textContent.trim())"
    )

    today_str = datetime.now(ZoneInfo(settings.timezone)).strftime(PORTAL_DATE_FORMAT)
    return _find_today_status(dates, working_holidays, leave_requests, today_str)


async def verify_portal_working_day(page: Page, settings: Settings) -> tuple[bool, str]:
    """
    Authoritative working-day check: reads today's row directly from the
    portal's own attendance table so real public holidays (Working Holiday
    != 'Business Day') and approved leave requests (Leave Request == 'Yes')
    are correctly treated as non-working days, unlike the naive Mon-Fri
    weekday check in `is_scheduled_working_day`.

    Returns (is_working_day, reason).
    """
    status = await get_portal_day_status(page, settings)
    if status is None:
        logger.warning("Could not locate today's row in the portal attendance table; falling back to weekday check")
        fallback = is_scheduled_working_day(settings)
        return fallback, "today's row not found on the portal table (used weekday fallback)"

    if status["working_holiday"] != BUSINESS_DAY_LABEL:
        return False, f"portal marks today as '{status['working_holiday']}'"

    if status["leave_request"].strip().lower() == LEAVE_REQUEST_YES.lower():
        return False, "an approved leave request exists for today"

    return True, "business day with no leave request"


async def random_delay(settings: Settings) -> float:
    """Sleep a random duration (in `settings` min/max minutes) to avoid predictable timestamps."""
    delay_seconds = random.uniform(settings.min_delay_minutes * 60, settings.max_delay_minutes * 60)
    logger.info("Injecting random delay of %.1f seconds before action", delay_seconds)
    await asyncio.sleep(delay_seconds)
    return delay_seconds


async def _login(page: Page, settings: Settings) -> None:
    """Log into the work portal. Raises on failure so callers can report errors."""
    if not (settings.portal_url and settings.portal_user and settings.portal_pass):
        raise RuntimeError("PORTAL_URL / PORTAL_USER / PORTAL_PASS are not configured")

    await page.goto(settings.portal_url, timeout=settings.login_timeout_ms, wait_until="domcontentloaded")

    await page.wait_for_selector(USERNAME_SELECTOR, timeout=settings.login_timeout_ms)
    await page.fill(USERNAME_SELECTOR, settings.portal_user)
    await page.fill(PASSWORD_SELECTOR, settings.portal_pass)
    await page.click(SUBMIT_SELECTOR)

    # Wait for navigation as proof of a successful login.
    await page.wait_for_load_state("networkidle", timeout=settings.login_timeout_ms)
    logger.info("Logged into portal successfully")


async def _goto_check_page(page: Page, settings: Settings) -> None:
    """Navigate to the dedicated check-in/out page if it differs from the current URL."""
    if settings.portal_check_url and settings.portal_check_url != page.url:
        await page.goto(settings.portal_check_url, timeout=settings.login_timeout_ms, wait_until="domcontentloaded")
        await page.wait_for_load_state("networkidle", timeout=settings.login_timeout_ms)


async def perform_action(action: str, settings: Settings) -> tuple[bool, str]:
    """
    Perform 'checkin' or 'checkout' on the portal using Playwright.

    Returns (success, message). On success, a full-page screenshot is saved to
    `settings.screenshot_path` as visual proof.
    """
    if action not in ("checkin", "checkout"):
        raise ValueError(f"Unsupported action: {action}")

    async with async_playwright() as pw:
        browser = None
        try:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            # NOTE: UI_TAT_028's attendance table (Webix datatable) virtualizes
            # rows and only renders as many as fit the viewport height. A tall
            # viewport forces the whole current month (~37 rows incl. blank
            # leading cells) to render so `verify_portal_working_day` can find
            # today's row without needing to scroll the grid.
            context = await browser.new_context(viewport={"width": 1366, "height": 2200})
            page = await context.new_page()

            await _login(page, settings)
            await _goto_check_page(page, settings)

            is_working_day, reason = await verify_portal_working_day(page, settings)
            if not is_working_day:
                await context.close()
                return False, f"⏭️ Skipped {action}: {reason}."

            await page.wait_for_selector(PUNCH_BUTTON_SELECTOR, timeout=settings.action_timeout_ms)
            await page.click(PUNCH_BUTTON_SELECTOR)

            # Give the portal a moment to reflect the state change before capturing proof.
            await page.wait_for_timeout(2000)
            await page.screenshot(path=settings.screenshot_path, full_page=True)

            await context.close()
            return True, f"✅ {action.capitalize()} completed successfully."

        except PlaywrightTimeoutError as exc:
            logger.exception("Timeout during %s", action)
            return False, f"⏱️ Timeout during {action}: {exc}"
        except Exception as exc:  # noqa: BLE001 - report all failures to Telegram
            logger.exception("Error during %s", action)
            return False, f"❌ Error during {action}: {exc}"
        finally:
            if browser is not None:
                try:
                    await browser.close()
                except Exception:
                    logger.exception("Failed to close browser cleanly")
