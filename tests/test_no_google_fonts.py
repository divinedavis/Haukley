"""haukley.com must never load fonts from Google (GDPR).

Loading Google Fonts from fonts.googleapis.com / fonts.gstatic.com sends every visitor's IP
address to Google without consent; LG Munich (3 O 17493/20, 2022) fined a site for exactly
that. Inter is self-hosted in web/fonts/ instead (OFL 1.1). This fails if a Google font host
comes back anywhere in the site, its generators (web/_src, scripts/) or the nginx CSPs.

The IMA ad SDK (imasdk.googleapis.com) and its hosts are a separate thing and are not
checked here.
"""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
GOOGLE_FONT_HOST = re.compile(r"fonts\.(?:googleapis|gstatic)\.com|fonts\.google\.com", re.I)
TEXT = {".html", ".inc", ".css", ".js", ".json", ".xml", ".txt", ".py", ".sh", ".conf", ".brs"}
SCANNED = [WEB, ROOT / "scripts", ROOT / "deploy", ROOT / "tvweb" / "src"]
CSS = [WEB / "site.css", WEB / "watch" / "app.css"]
WOFF2 = ["inter-latin.woff2", "inter-latin-ext.woff2"]


def text_files():
    for base in SCANNED:
        for p in base.rglob("*"):
            if p.is_file() and p.suffix in TEXT and "node_modules" not in p.parts and "dist" not in p.parts:
                yield p


def csps():
    conf = (ROOT / "deploy" / "nginx-haukley.conf").read_text()
    return re.findall(r'Content-Security-Policy "([^"]+)"', conf)


class NoGoogleFonts(unittest.TestCase):
    def test_no_google_font_host_anywhere(self):
        hits = []
        for p in text_files():
            for n, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
                if GOOGLE_FONT_HOST.search(line):
                    hits.append(f"{p.relative_to(ROOT)}:{n}")
        self.assertEqual(hits, [], "Google font host found (self-host in web/fonts/ instead)")

    def test_csps_allow_only_self_hosted_fonts(self):
        policies = csps()
        self.assertGreaterEqual(len(policies), 2, "expected the site CSP and /watch's own CSP")
        for csp in policies:
            if "default-src 'none'" in csp:
                continue  # /ads/ XML: loads nothing at all
            d = {x.split()[0]: x.split()[1:] for x in (y.strip() for y in csp.split(";")) if x}
            self.assertEqual(d.get("font-src"), ["'self'"], csp)
            self.assertNotIn("https://fonts.googleapis.com", d.get("style-src", []), csp)

    def test_inter_is_self_hosted(self):
        for name in WOFF2:
            f = WEB / "fonts" / name
            self.assertTrue(f.is_file(), f)
            self.assertEqual(f.read_bytes()[:4], b"wOF2", f"{f} is not a woff2 file")
        self.assertTrue((WEB / "fonts" / "Inter-LICENSE.txt").is_file(), "ship the OFL with the font")
        for css in CSS:
            faces = re.findall(r"@font-face\s*{[^}]*}", css.read_text())
            inter = [f for f in faces if '"Inter"' in f]
            self.assertEqual(len(inter), 2, f"{css.name}: Inter latin + latin-ext @font-face")
            for f in inter:
                self.assertIn("font-display: swap", f)
                self.assertRegex(f, r"url\(/fonts/inter-latin(-ext)?\.woff2\)")
            self.assertEqual(sorted(re.findall(r"/fonts/(inter-[a-z-]+\.woff2)", " ".join(inter))), sorted(WOFF2))


if __name__ == "__main__":
    unittest.main()
