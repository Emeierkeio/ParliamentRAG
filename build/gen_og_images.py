#!/usr/bin/env python
"""
Regenerate the Open Graph preview images from the live site.

Each image is a screenshot of the page with the top status strip cropped off,
so the preview never carries the volatile "dati aggiornati al ..." date and
does not need re-generating on every data update. Output lands in the Next.js
`opengraph-image.png` file-convention slots, one per route.

Run:  make og-images        (or: backend/venv/bin/python build/gen_og_images.py)
Needs Playwright + Pillow in backend/venv (both already installed).
"""
import io
import pathlib

from PIL import Image
from playwright.sync_api import sync_playwright

W, H = 1200, 630          # OG canonical box
SCALE = 2                 # render at 2x for retina crispness
MAX_BAR = 40              # tallest top crop, so the capture viewport fits any page
BASE = "https://www.parliamentrag.it"
ROOT = pathlib.Path(__file__).resolve().parent.parent / "frontend" / "src" / "app"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# route -> (destination, top crop in px at 1x). Only the landing carries the
# "DATI AGGIORNATI AL ..." strip, so only it is cropped. /home and /data lead
# with their own header, which must stay intact (crop 0).
PAGES = {
    "/":     (ROOT / "opengraph-image.png", 34),
    "/home": (ROOT / "home" / "opengraph-image.png", 0),
    "/data": (ROOT / "data" / "opengraph-image.png", 0),
}


def main() -> None:
    with sync_playwright() as p:
        # QUIC/HTTP2 off + no automation flag: the CDN resets plain headless
        browser = p.chromium.launch(args=[
            "--no-sandbox", "--disable-quic", "--disable-http2",
            "--disable-blink-features=AutomationControlled",
        ])
        ctx = browser.new_context(
            viewport={"width": W, "height": H + MAX_BAR},
            device_scale_factor=SCALE, user_agent=UA, ignore_https_errors=True,
        )
        page = ctx.new_page()
        for route, (out, bar) in PAGES.items():
            for attempt in range(3):
                try:
                    page.goto(BASE + route, wait_until="commit", timeout=45000)
                    break
                except Exception as e:  # transient CDN reset
                    print(f"  retry {route}: {str(e)[:60]}")
                    page.wait_for_timeout(1500)
            # wait for async fetches (graph-sample, stats, topics) to finish,
            # then a short settle so the SVG graph is painted before capture
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            page.wait_for_timeout(3000)
            img = Image.open(io.BytesIO(page.screenshot()))
            top = bar * SCALE
            img = img.crop((0, top, W * SCALE, top + H * SCALE))
            out.parent.mkdir(parents=True, exist_ok=True)
            img.save(out)
            print(f"{route} -> {out.relative_to(ROOT.parent.parent)} ({img.size[0]}x{img.size[1]})")
        browser.close()


if __name__ == "__main__":
    main()
