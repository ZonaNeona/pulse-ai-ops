"""Screenshots of every screen in both themes and three widths — for design review and the README.

Usage: python tools/shoot.py [base_url] [out_dir]
Defaults: http://localhost:5180, docs/screenshots. Needs `pip install playwright && playwright install chromium`.
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROUTES = {
    "overview": "/",
    "sales": "/sales",
    "team": "/sales/team",
    "deals": "/sales/deals",
    "calls": "/sales/calls",
    "docs": "/docs",
    "knowledge": "/knowledge",
    "integrations": "/integrations",
    "copilot": "/copilot",
    "under-the-hood": "/under-the-hood",
    "design": "/design",
}
WIDTHS = {"desktop": (1440, 900), "tablet": (768, 1024), "mobile": (390, 844)}
THEMES = ("light", "dark")


def main() -> None:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5180"
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "docs/screenshots")
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for theme in THEMES:
            for size_name, (w, h) in WIDTHS.items():
                ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, locale="ru-RU")
                ctx.add_init_script(f"localStorage.setItem('pulse-theme', '{theme}')")
                page = ctx.new_page()
                for name, route in ROUTES.items():
                    page.goto(f"{base}/#{route}")
                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(600)  # entrance animations
                    page.screenshot(path=out / f"{name}-{theme}-{size_name}.png", full_page=size_name != "desktop")
                ctx.close()
        browser.close()
    print(f"saved {len(ROUTES) * len(WIDTHS) * len(THEMES)} screenshots to {out}")


if __name__ == "__main__":
    main()
