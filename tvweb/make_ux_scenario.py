"""UX Scenario PDF for LG Seller Lounge QA (Test Info > "Upload a UX Scenario File").

Built from the journey test's screenshots, so run the test first:
  ~/.venvs/dhcr-map/bin/python tvweb/test_journey.py
  ~/.venvs/dhcr-map/bin/python tvweb/make_ux_scenario.py
-> marketing/lg/Haukley-UX-Scenario.pdf (LG's limit is 10 MB)
"""
import base64
import html
import io
import pathlib

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHOTS = ROOT / "tvweb" / "dist" / "journey"
OUT = ROOT / "marketing" / "lg" / "Haukley-UX-Scenario.pdf"

# (screenshot, title, what the tester does and sees)
STEPS = [
    ("1-home", "1. Launch and Home",
     ["Launch Haukley from the launcher. No login, account, voucher or age gate: the app opens straight to Home.",
      "Focus starts on Play in the featured banner, which rotates through featured titles every 9 seconds.",
      "Below it: Continue Watching (after something has been watched) and rows by genre, Top 10 and TV shows."]),
    ("2-rows", "2. Browsing rows",
     ["UP/DOWN moves between the tab bar, the banner and each row; LEFT/RIGHT moves along a row.",
      "Magic Remote: pointing at a poster highlights it, OK/click opens it, the wheel moves between rows.",
      "Pressing any arrow key hides the pointer and returns to key navigation."]),
    ("3-detail", "3. Title page",
     ["OK on a poster opens its title page: year, genre, running time, rating, description, credits.",
      "Play (or Resume from the saved position, with Start Over), the license line, and More Like This below.",
      "Films with a content advisory show it on this page (see step 10)."]),
    ("9-episodes", "4. TV shows and episodes",
     ["The Shows tab lists every series. A show's title page lists its episodes with length and summary.",
      "OK on an episode plays it; Play resumes the latest episode or starts the next one.",
      "Progress is saved per episode and appears in Continue Watching on Home."]),
    ("6-player", "5. Player and ads",
     ["Playback starts after an optional ad break. Ads are Google IMA (VMAP) pre-rolls and mid-rolls; while an ad plays the "
      "controls are hidden and seeking is disabled. If no ad is returned the film starts immediately.",
      "A rating card (and any content advisory) shows for 5-8 seconds when the film begins.",
      "OK or click: play/pause. LEFT/RIGHT (and FF/RW keys): skip 10 s. PLAY/PAUSE/STOP media keys work.",
      "BACK or STOP closes the player and returns to the title page with the position saved."]),
    ("4-search", "6. Search",
     ["The Search tab has an on-screen keyboard (A-Z, 0-9, SPACE, DELETE). Results update as you type.",
      "RIGHT from the keyboard moves into the results; OK opens a title."]),
    ("8-shows", "7. Movies and Shows tabs",
     ["Movies lists every film by genre; Shows lists every series by genre."]),
    ("7-exit", "8. BACK key and exiting",
     ["BACK always goes one screen back: player > title page > the tab you came from > Home.",
      "BACK on Home shows \"Exit Haukley?\" with Cancel focused. Cancel stays in the app; Exit closes it."]),
    ("10-advisory", "9. Content advisories",
     ["Titles with violence or other sensitive content show an Advisory line on the title page and on the "
      "rating card at the start of playback."]),
]

NOTES = [
    ("Account / login", "None. The app has no sign-in, no account and no age verification."),
    ("Payment", "None. Every title is free; there are no purchases or subscriptions."),
    ("Adult content", "None. The catalog is classic public-domain and Creative Commons film and TV (rated 18+ for "
                      "classic horror and war violence)."),
    ("Network", "Needs an internet connection. The catalog loads from haukley.com (a packaged copy is the fallback) "
                "and video streams over HLS from a DigitalOcean CDN. Without a connection the app says so on launch."),
    ("Remote", "Standard remote (arrows, OK, BACK, media keys) and the Magic Remote pointer and wheel."),
    ("Service country", "United States only (the films are public domain in the US)."),
    ("Contact", "support@haukley.com"),
]


def img_data(name):
    im = Image.open(SHOTS / f"{name}.png").convert("RGB")
    im.thumbnail((1280, 720))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=78, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def main():
    steps = "".join(
        f"""<section><h2>{html.escape(t)}</h2><img src="{img_data(s)}">
        <ul>{"".join(f"<li>{html.escape(b)}</li>" for b in bullets)}</ul></section>"""
        for s, t, bullets in STEPS)
    notes = "".join(f"<tr><th>{html.escape(k)}</th><td>{html.escape(v)}</td></tr>" for k, v in NOTES)
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><style>
      body {{ font-family: -apple-system, Helvetica, Arial, sans-serif; color: #111; margin: 0; }}
      .cover {{ page-break-after: always; padding: 40px 10px; }}
      h1 {{ font-size: 30px; margin: 0 0 6px; }}
      .sub {{ color: #555; font-size: 14px; margin-bottom: 26px; }}
      table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
      th, td {{ text-align: left; vertical-align: top; padding: 8px 10px; border-bottom: 1px solid #ddd; }}
      th {{ width: 150px; }}
      section {{ page-break-inside: avoid; page-break-after: always; padding-top: 10px; }}
      h2 {{ font-size: 20px; margin: 0 0 10px; }}
      img {{ display: block; height: 120mm; width: auto; border: 1px solid #ccc; }}  /* one step per landscape page */
      ul {{ font-size: 13px; line-height: 1.5; padding-left: 20px; }}
    </style></head><body>
      <div class="cover"><h1>Haukley — UX Scenario</h1>
        <div class="sub">webOS TV app com.haukley.tv, version 1.0.0 · 1920x1080 · webOS 4.0 (2018) and later</div>
        <p style="font-size:14px;line-height:1.5">Haukley is a free, ad-supported streaming app of classic movies and TV
        shows. This document walks through every screen in the order a viewer meets them, with the remote keys for each.</p>
        <table>{notes}</table></div>
      {steps}
    </body></html>"""
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        page.set_content(doc, wait_until="load")
        page.pdf(path=str(OUT), format="A4", landscape=True, print_background=True,
                 margin={"top": "14mm", "bottom": "14mm", "left": "14mm", "right": "14mm"})
        b.close()
    print(f"{OUT.relative_to(ROOT)}  {OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
