"""The catalog every platform ships, checked before it can reach a viewer.

scripts/catalog.json + scripts/rows.json are the source; make_web.py, make_ios.py and
make_roku.py write a copy per platform. These tests catch the mistakes that otherwise only
show up on a TV: a row pointing at a title that doesn't exist (empty tile), a title with no
rights line (App Review / CC BY attribution), a stream off the CDN or on http (blocked by
ATS / mixed content), missing art, and a platform copy left stale after a catalog edit.
"""
import json
import pathlib
import unittest
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
CDN = "haukley-media.nyc3.cdn.digitaloceanspaces.com"


def load(rel):
    return json.loads((ROOT / rel).read_text())


SOURCE = load("scripts/catalog.json")
ROWS = load("scripts/rows.json")
SRC_TITLES = {t["id"]: t for key in ("movies", "shows", "live") for t in SOURCE.get(key, [])}
LIVE_IDS = {t["id"] for t in SOURCE.get("live", [])}
# Live channels are encoded on the droplet (live/, deploy/deploy_weather.sh), not the CDN.
LIVE_HOST, LIVE_PREFIX = "haukley.com", "/live/"
# Titles sourced in scripts/free_titles*.json but held back (rights review, sponsor cuts).
# rows.json may already list one so it shows up the day it is cleared; the apps skip ids
# they don't have. Any OTHER unknown row id is a typo and leaves a hole in the row.
HELD = {t["id"] for p in sorted((ROOT / "scripts").glob("free_titles*.json"))
        for t in json.loads(p.read_text())} - set(SRC_TITLES)

COPIES = {
    "web": load("web/watch/catalog/catalog.json"),
    "iphone": load("iphone/Haukley/Resources/Catalog/catalog.json"),
    "roku": load("roku/data/catalog.json"),
}


def titles_of(copy):
    t = copy["titles"]
    return t if isinstance(t, dict) else {x["id"]: x for x in t}


def row_ids(row):
    return row["ids"] if "ids" in row else [i["id"] for i in row["items"]]


def streams(title):
    if title.get("stream"):
        yield title["id"], title["stream"]
    for ep in title.get("episodes") or []:
        if ep.get("stream"):
            yield f'{title["id"]} ep {ep.get("number")}', ep["stream"]


class SourceCatalog(unittest.TestCase):
    def test_ids_unique_across_movies_and_shows(self):
        ids = [t["id"] for key in ("movies", "shows", "live") for t in SOURCE.get(key, [])]
        self.assertEqual(len(ids), len(set(ids)), "duplicate title id in scripts/catalog.json")

    def test_every_title_has_rights_line_and_text(self):
        for tid, t in SRC_TITLES.items():
            for field in ("title", "license", "description", "genre", "rating"):
                self.assertTrue(str(t.get(field, "")).strip(), f"{tid} has no {field}")

    def test_movies_stream_and_shows_have_episode_streams(self):
        for t in SOURCE["movies"]:
            self.assertTrue(t.get("stream"), f'{t["id"]} has no stream')
        for t in SOURCE.get("live", []):
            self.assertTrue(t.get("stream"), f'{t["id"]} has no stream')
            self.assertFalse(t.get("episodes") or t.get("runtime"), f'{t["id"]}: live has no runtime/episodes')
        for t in SOURCE["shows"]:
            self.assertTrue(t.get("episodes"), f'{t["id"]} has no episodes')
            for ep in t["episodes"]:
                self.assertTrue(ep.get("stream"), f'{t["id"]} ep {ep.get("number")} has no stream')

    def test_stills_exist(self):
        for tid, t in SRC_TITLES.items():
            if t.get("still"):
                self.assertTrue((ROOT / t["still"]).is_file(), f'{tid}: missing {t["still"]}')

    def test_rows_point_at_real_or_held_titles(self):
        for tid in ROWS["featured"]:
            self.assertTrue(tid in SRC_TITLES, f"featured id {tid} not in catalog")
        for row in ROWS["home"]:
            for tid in row.get("ids", []):
                self.assertTrue(tid in SRC_TITLES or tid in HELD,
                                f'row {row["key"]}: {tid} is neither in the catalog nor a held title')


class PlatformCopies(unittest.TestCase):
    def test_same_titles_as_source(self):
        for name, copy in COPIES.items():
            got = set(titles_of(copy))
            self.assertEqual(got, set(SRC_TITLES),
                             f"{name} catalog is stale vs scripts/catalog.json "
                             f"(missing {sorted(set(SRC_TITLES) - got)[:5]}, "
                             f"extra {sorted(got - set(SRC_TITLES))[:5]}) - rerun make_web/make_ios/make_roku")

    def test_rows_resolve(self):
        for name, copy in COPIES.items():
            titles = titles_of(copy)
            self.assertTrue(copy["rows"], f"{name} has no rows")
            for row in copy["rows"]:
                ids = row_ids(row)
                self.assertTrue(any(t in titles for t in ids), f'{name} row {row["key"]} is empty')
                for tid in ids:
                    # A ranked row numbers its tiles, so a skipped id would misnumber it.
                    ok = tid in titles or (tid in HELD and row.get("type") != "ranked")
                    self.assertTrue(ok, f'{name} row {row["key"]}: {tid} missing')
            for tid in copy.get("featured", []):
                self.assertTrue(tid in titles, f"{name} featured {tid} missing")

    def test_rights_line_survives_every_copy(self):
        for name, copy in COPIES.items():
            for tid, t in titles_of(copy).items():
                self.assertTrue(t.get("license", "").strip(), f"{name}: {tid} lost its license line")

    def test_streams_are_https_on_the_cdn(self):
        for name, copy in COPIES.items():
            for tid, t in titles_of(copy).items():
                for label, url in streams(t):
                    u = urlparse(url)
                    self.assertEqual(u.scheme, "https", f"{name} {label}: {url}")
                    if tid in LIVE_IDS:
                        self.assertEqual(u.netloc, LIVE_HOST, f"{name} {label}: {url}")
                        self.assertTrue(u.path.startswith(LIVE_PREFIX), f"{name} {label}: {url}")
                        continue
                    self.assertEqual(u.netloc, CDN, f"{name} {label}: stream off the CDN: {url}")
                    self.assertTrue(u.path.endswith(".m3u8"), f"{name} {label}: not HLS: {url}")

    def test_bundled_art_exists(self):
        for base in ("web/watch/catalog", "iphone/Haukley/Resources/Catalog"):
            for tid in SRC_TITLES:
                for img in ("poster.jpg", "card.jpg", "backdrop.jpg"):
                    self.assertTrue((ROOT / base / tid / img).is_file(), f"missing {base}/{tid}/{img}")

    def test_roku_art_urls_are_in_the_web_docroot(self):
        # Roku loads art from https://haukley.com/roku/img/..., served from web/roku/img/.
        for tid, t in titles_of(COPIES["roku"]).items():
            urls = [t.get(k) for k in ("poster", "card", "backdrop")]
            urls += [ep.get("still") for ep in t.get("episodes") or []]
            for url in filter(None, urls):
                u = urlparse(url)
                self.assertEqual(u.netloc, "haukley.com", f"roku {tid}: {url}")
                self.assertTrue((ROOT / "web" / u.path.lstrip("/")).is_file(),
                                f"roku {tid}: {url} has no file under web/")


if __name__ == "__main__":
    unittest.main()

    def test_live_channels_are_kind_live_in_every_copy(self):
        for name, copy in COPIES.items():
            titles = titles_of(copy)
            for tid in LIVE_IDS:
                self.assertIn(tid, titles, f"{name}: live channel {tid} missing")
                self.assertEqual(titles[tid].get("kind"), "live", f"{name}: {tid} is not kind live")



def test_every_catalog_title_is_seeded_in_a_migration():
    # start_playback refuses ids missing from public.titles (no ad ticket, no play logged), and
    # ad_events.title_id references that table. 34 titles shipped unseeded until 0017.
    import re
    seeded = set()
    for p in sorted((ROOT / "supabase" / "migrations").glob("*.sql")):
        seeded |= set(re.findall(r"\(\s*'([a-z0-9-]+)',\s*'(?:movie|show)'", p.read_text()))
    missing = sorted(tid for key in ("movies", "shows") for tid in (t["id"] for t in SOURCE[key]) if tid not in seeded)
    assert not missing, f"add these to a supabase migration's titles insert (then apply it): {missing}"
