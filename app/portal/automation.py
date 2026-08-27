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


def is_scheduled_working_day(settings: Settings, reference: datetime | None = None) -> bool:
    """Return True if `reference` (default: now, in `settings.timezone`) is a working day."""
    now = reference or datetime.now(ZoneInfo(settings.timezone))
    return now.weekday() in settings.working_days


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
            context = await browser.new_context(viewport={"width": 1366, "height": 768})
            page = await context.new_page()

            await _login(page, settings)
            await _goto_check_page(page, settings)

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
