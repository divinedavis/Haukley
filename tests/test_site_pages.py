"""The crawlable catalog pages built by scripts/make_site_pages.py.

- the generated files match a fresh build (catalog, rows, head.inc or the script changed and
  nobody re-ran it);
- every movie and show in the web catalog has a /films/<id>/ page that links into /watch,
  and the sitemap lists it;
- the homepage shows real catalog posters, not the old placeholder lineup;
- every page carries the AdSense site-verification meta tag.
"""
import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
spec = importlib.util.spec_from_file_location("make_site_pages", ROOT / "scripts" / "make_site_pages.py")
msp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(msp)
CAT = json.loads((WEB / "watch" / "catalog" / "catalog.json").read_text())
IDS = [t["id"] for t in CAT["titles"] if t["kind"] in ("movie", "show")]


class SitePages(unittest.TestCase):
    def test_generated_files_are_fresh(self):
        for rel, text in msp.build().items():
            self.assertTrue((WEB / rel).is_file() and (WEB / rel).read_text() == text,
                            f"web/{rel} is stale - run python3 scripts/make_site_pages.py")

    def test_no_orphan_title_pages(self):
        pages = {p.name for p in (WEB / "films").iterdir() if p.is_dir()}
        self.assertEqual(pages, set(IDS))

    def test_every_title_has_a_page_in_the_sitemap(self):
        sitemap = (WEB / "sitemap.xml").read_text()
        for i in IDS:
            page = (WEB / "films" / i / "index.html").read_text()
            self.assertIn(f'href="/watch/#/title/{i}"', page)
            self.assertIn("free to watch", page)
            self.assertIn(f"https://haukley.com/films/{i}/", sitemap)
        self.assertIn("Sitemap: https://haukley.com/sitemap.xml", (WEB / "robots.txt").read_text())

    def test_every_collection_note_matches_a_row(self):
        keys = {r["key"] for r in CAT["rows"]}
        self.assertFalse(set(msp.NOTES) - keys, "NOTES key with no app row")
        self.assertFalse(set(msp.HOME_ROWS) - keys)

    def test_homepage_has_no_placeholder_lineup(self):
        home = (WEB / "index.html").read_text()
        for gone in ("preview of what's coming", "Artwork shown is a preview", "/img/night-line", "Google TV"):
            self.assertNotIn(gone, home)
        self.assertIn('href="/films/metropolis/"', home)

    def test_adsense_meta_on_every_page(self):
        tag = '<meta name="google-adsense-account" content="ca-pub-8077227518694725">'
        for p in WEB.rglob("index.html"):
            if p.parent.name in ("watch", "_src") or "watch" in p.parts:
                continue
            self.assertIn(tag, p.read_text(), p)


if __name__ == "__main__":
    unittest.main()
