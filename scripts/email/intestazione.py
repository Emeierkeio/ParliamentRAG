"""Rende le immagini delle email in public/email/ (a 2x):
- scripts/email/intestazione.html -> intestazione@2x.png (1120x152)
- scripts/email/seggi.html -> seggi@2x.png (1600x840, trasparente), lo sfondo
  dietro il riquadro dei modelli Brevo."""
from pathlib import Path

from playwright.sync_api import sync_playwright

QUI = Path(__file__).resolve().parent
EMAIL = QUI.parent.parent / "public" / "email"

with sync_playwright() as p:
    browser = p.chromium.launch()
    for nome, w, h, trasparente in (("intestazione", 560, 76, False), ("seggi", 800, 420, True)):
        page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=2)
        page.goto((QUI / f"{nome}.html").as_uri())
        page.wait_for_timeout(500)
        page.screenshot(path=str(EMAIL / f"{nome}@2x.png"), omit_background=trasparente)
        page.close()
    browser.close()
print("ok")
