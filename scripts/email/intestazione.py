"""Rende scripts/email/intestazione.html in public/email/intestazione@2x.png
(1120x320, mostrata a 560x160 nelle email)."""
from pathlib import Path

from playwright.sync_api import sync_playwright

QUI = Path(__file__).resolve().parent
USCITA = QUI.parent.parent / "public" / "email" / "intestazione@2x.png"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 560, "height": 160}, device_scale_factor=2)
    page.goto((QUI / "intestazione.html").as_uri())
    page.wait_for_timeout(500)
    page.screenshot(path=str(USCITA))
    browser.close()
print(USCITA)
