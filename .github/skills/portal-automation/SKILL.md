---
name: portal-automation
description: Directs Copilot on how to expand web scraping, check-in/out logic, and DOM interactions with Playwright. Use when modifying schedule checks or adding portal features.
---

# Web Automation Rules

1. **Selector Priority:** Use `page.get_by_role()`, `page.get_by_label()`, or explicit IDs over dynamic CSS paths.
2. **Navigation Safety:** Always await `page.wait_for_load_state("networkidle")` after login or form submissions.
3. **Randomization:** Incorporate random delays using `asyncio.sleep(random.randint(min_sec, max_sec))` before executing actionable clicks (check-in/out) to simulate human behavior.
4. **Visual Verification:** Always capture a screenshot of confirmation popups or status badges (`await page.screenshot(path="proof.png")`) to return to the Telegram handler.

## Working-Day Verification (UI_TAT_028 attendance table)

The portal's own attendance table (`UI_TAT_028`) is the **authoritative**
source of whether today is a working day — not a hardcoded Mon-Fri check.
It renders one column per field, each as `div[column="N"] div[role="gridcell"]`,
with matching row order across columns:

| Column | Field | Example values |
|---|---|---|
| 0 | Date | `Aug 27, 2026` (format `%b %d, %Y`) |
| 3 | Working Holiday | `Business Day`, `Weekend` (or a holiday name) |
| 4 | Leave Request | `Yes` if an approved leave exists, empty otherwise |

`app/portal/automation.py` implements this as two layers:
- `is_scheduled_working_day()` — cheap, offline Mon-Fri heuristic, used only
  to skip launching a browser at all on weekends (before Playwright starts).
- `verify_portal_working_day()` — the authoritative check: scrapes today's
  row from the table already loaded in `page` and returns `(False, reason)`
  if Working Holiday != `"Business Day"` or Leave Request == `"Yes"`. Always
  run this *after* login/navigation and *before* clicking the punch button,
  and treat a `False` result as a normal skip (not an error) — reply to the
  user, but don't send a screenshot.

When extending this logic (e.g. new columns, different date formats), keep
the DOM-scraping (`get_portal_day_status`, async, requires `page`) separate
from the pure row-matching logic (`_find_today_status`, sync) so the matching
logic stays unit-testable without a real browser (see `tests/test_portal_automation.py`).

