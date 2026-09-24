"""Assemble the subpages (shared header/footer + body) into web/<page>/index.html.
Usage: python3 web/_src/build.py"""
import pathlib

SRC = pathlib.Path(__file__).resolve().parent
WEB = SRC.parent
PAGES = {
    "filmmakers": ("Haukley for Filmmakers — Free distribution, 50% of ad revenue",
                   "Get your film on Roku, Fire TV, Google TV, Apple TV and iPhone. No fees, non-exclusive, and 50% of the ad revenue your film earns, paid monthly.",
                   '<script src="/site.js"></script>\n  <script>Haukley.waitlist("notify-films", "filmmakers");</script>\n'),
    "privacy": ("Privacy Policy — Haukley", "How Haukley collects, uses and protects information.", ""),
    "terms": ("Terms of Use — Haukley", "The terms for using haukley.com and the Haukley apps.", ""),
    "support": ("Support — Haukley", "Get help with the Haukley apps.", ""),
}
head = (SRC / "head.inc").read_text()
foot = (SRC / "foot.inc").read_text()
for page, (title, desc, scripts) in PAGES.items():
    body = (SRC / f"{page}.body.html").read_text()
    html = head.replace("__TITLE__", title).replace("__DESC__", desc).replace("__PATH__", f"/{page}/")
    html += body + foot + ("  " + scripts if scripts else "") + "</body>\n</html>\n"
    out = WEB / page / "index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(html)
    print("built", out.relative_to(WEB))
