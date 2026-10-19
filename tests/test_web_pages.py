"""Static checks on the haukley.com docroot (web/) before scripts/deploy_web.sh copies it.

- every shipped page has a viewport meta and a <title> (a missing viewport meta renders
  the desktop layout shrunk on iPhones and hides behind iframe test harnesses);
- the subpages built from web/_src are not stale (someone edited a .body.html or head.inc
  and never ran web/_src/build.py, or hand-edited the output);
- every local script/stylesheet a page references exists;
- ads.txt keeps the AdSense seller line; app-ads.txt stays well-formed.
"""
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
# google<token>.html is Search Console's one-line verification file, not a page.
PAGES = sorted(p for p in WEB.rglob("*.html") if "_src" not in p.parts and not p.name.startswith("google"))
PUB = "pub-8077227518694725"


class WebPages(unittest.TestCase):
    def test_pages_found(self):
        self.assertGreaterEqual(len(PAGES), 6, PAGES)

    def test_viewport_and_title(self):
        for p in PAGES:
            html = p.read_text()
            self.assertRegex(html, r'<meta name="viewport"[^>]*width=device-width', f"{p} has no viewport meta")
            self.assertRegex(html, r"<title>[^<]+</title>", f"{p} has no <title>")

    def test_local_assets_exist(self):
        for p in PAGES:
            for ref in re.findall(r'(?:src|href)="([^"]+\.(?:js|css|png|jpg|woff2))(?:\?[^"]*)?"', p.read_text()):
                if ref.startswith(("http:", "https:", "//", "data:")):
                    continue
                target = (WEB / ref.lstrip("/")) if ref.startswith("/") else (p.parent / ref)
                self.assertTrue(target.is_file(), f"{p.relative_to(ROOT)} references missing {ref}")

    def test_built_subpages_match_their_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(WEB / "_src", pathlib.Path(tmp) / "_src")
            subprocess.run([sys.executable, str(pathlib.Path(tmp) / "_src" / "build.py")],
                           check=True, capture_output=True)
            built = [d for d in pathlib.Path(tmp).iterdir() if d.name != "_src"]
            self.assertTrue(built)
            for d in built:
                fresh = (d / "index.html").read_text()
                live = (WEB / d.name / "index.html").read_text()
                self.assertTrue(fresh == live, f"web/{d.name}/index.html is stale - run python3 web/_src/build.py")

    def test_ads_txt_seller_lines(self):
        self.assertIn(PUB, (WEB / "ads.txt").read_text())
        # app-ads.txt holds the IAB "no authorized sellers" placeholder until Ad Manager
        # exists; Roku and the app stores only need a well-formed seller line.
        lines = [l for l in (WEB / "app-ads.txt").read_text().splitlines() if l.strip() and not l.startswith("#")]
        self.assertTrue(lines and all(len(l.split(",")) >= 3 for l in lines), lines)


if __name__ == "__main__":
    unittest.main()


def _watch_csp():
    import re
    conf = (ROOT / "deploy" / "nginx-haukley.conf").read_text()
    block = conf[conf.index("location /watch/ {"):]
    block = block[:block.index("}")]
    m = re.search(r'Content-Security-Policy "([^"]+)"', block)
    assert m, "no CSP in location /watch/"
    return {d.split()[0]: d.split()[1:] for d in (x.strip() for x in m.group(1).split(";")) if d}


def test_watch_csp_has_no_inline_scripts_or_open_connect():
    csp = _watch_csp()
    assert "'unsafe-inline'" not in csp["script-src"] and "'unsafe-eval'" not in csp["script-src"]
    assert "https:" not in csp["connect-src"] and "*" not in csp["connect-src"]
    for host in ("https://axgxpwgbpgcqjxoqwtnv.supabase.co", "https://haukley-media.nyc3.cdn.digitaloceanspaces.com",
                 "https://imasdk.googleapis.com"):
        assert host in csp["connect-src"], host


def test_watch_page_has_no_inline_script():
    import re
    html = (ROOT / "web" / "watch" / "index.html").read_text()
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html), "inline <script> in /watch/ (CSP blocks it)"
    assert not re.search(r"\son[a-z]+=", html), "inline event handler in /watch/ (CSP blocks it)"


def test_catalog_streams_are_on_the_csp_cdn():
    import json
    csp = _watch_csp()
    cat = json.loads((ROOT / "web" / "watch" / "catalog" / "catalog.json").read_text())
    urls = [t["stream"] for t in cat["titles"] if t.get("stream")]
    urls += [e["stream"] for t in cat["titles"] for e in t.get("episodes", []) if e.get("stream")]
    hosts = {"/".join(u.split("/")[:3]) for u in urls}
    # /watch/ is served from haukley.com, so 'self' covers the live channels (/live/).
    allowed = set(csp["connect-src"]) | ({"https://haukley.com"} if "'self'" in csp["connect-src"] else set())
    assert hosts and hosts <= allowed, hosts - allowed


def test_local_weather_privacy_rules():
    """/watch local weather: same-origin API, location asked only from the explicit button,
    nginx logs nothing for /api/weather/ and never forwards a client X-Forwarded-For, and the
    privacy policy says so (owner rule 2026-10-10)."""
    js = (WEB / "watch" / "app.js").read_text()
    assert 'fetch(`/api/weather/local' in js and 'fetch("/api/weather/cities")' in js
    assert js.count("getCurrentPosition") == 1, "geolocation must only be requested in one place"
    gps = js[js.index('e.target.closest("[data-wx-gps]")'):]
    assert gps.index("getCurrentPosition") < 400, "geolocation must sit inside the [data-wx-gps] click branch"
    assert "toFixed(2)" in gps[:600], "device location is rounded before it leaves the browser"
    conf = (ROOT / "deploy" / "nginx-haukley.conf").read_text()
    loc = conf[conf.index("location /api/weather/ {"):]
    loc = loc[:loc.index("}")]
    assert "access_log off;" in loc and 'proxy_set_header X-Forwarded-For "";' in loc
    assert "proxy_set_header X-Real-IP $remote_addr;" in loc
    privacy = (WEB / "privacy" / "index.html").read_text()
    assert "Use my exact location" in privacy and "DB-IP" in privacy and "Not stored and not logged" in privacy
