---
name: portal-automation
description: Directs Copilot on how to expand web scraping, check-in/out logic, and DOM interactions with Playwright. Use when modifying schedule checks or adding portal features.
---

# Web Automation Rules

1. **Selector Priority:** Use `page.get_by_role()`, `page.get_by_label()`, or explicit IDs over dynamic CSS paths.
2. **Navigation Safety:** Always await `page.wait_for_load_state("networkidle")` after login or form submissions.
3. **Randomization:** Incorporate random delays using `asyncio.sleep(random.randint(min_sec, max_sec))` before executing actionable clicks (check-in/out) to simulate human behavior.
4. **Visual Verification:** Always capture a screenshot of confirmation popups or status badges (`await page.screenshot(path="proof.png")`) to return to the Telegram handler.
