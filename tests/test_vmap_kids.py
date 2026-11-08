"""COPPA: child-directed titles must never get ads, on any platform.

Every app (web, iPhone, tvOS, Fire TV, Roku, LG, Samsung) builds its ad tag from
haukley.com/ads/vmap/<title id>.xml (scripts/ads.json); series episodes use the show's id.
So scripts/make_vmap.py is the server-side control: a kids title's VMAP may reference
NO_AD_TAG and nothing else - today, AND after a real Google Ad Manager VAST_TAG is set.
The /watch player also requests no ads at all on a Kids profile.
"""
import contextlib
import importlib.util
import io
import json
import pathlib
import re
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
CATALOG = json.loads((ROOT / "scripts" / "catalog.json").read_text())
VMAP_DIR = ROOT / "web" / "ads" / "vmap"
FAKE_GAM = ("https://pubads.g.doubleclick.net/gampad/ads?iu=/1234/haukley&sz=640x480&gdfp_req=1"
            "&output=vast&env=vp&cust_params={cust}")


def load_make_vmap():
    spec = importlib.util.spec_from_file_location("make_vmap", ROOT / "scripts" / "make_vmap.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MV = load_make_vmap()
TITLES = [t for key in ("movies", "shows") for t in CATALOG[key]]
KIDS = [t for t in TITLES if MV.child_directed(t)]


def tags(xml):
    return re.findall(r"<vmap:AdTagURI[^>]*>\s*<!\[CDATA\[(.*?)\]\]>\s*</vmap:AdTagURI>", xml, re.S)


class KidsTitlesGetNoAds(unittest.TestCase):
    def test_every_kids_flag_is_child_directed(self):
        flagged = {t["id"] for t in TITLES if t.get("kids")}
        flagged |= {t["id"] for t in TITLES for e in t.get("episodes") or [] if e.get("kids")}
        self.assertGreaterEqual(len(flagged), 20, "the catalog's kids flag went missing?")
        self.assertLessEqual(flagged, {t["id"] for t in KIDS})
        for rating in ("TV-Y", "TV-Y7"):
            self.assertTrue(MV.child_directed({"id": "x", "rating": rating, "kids": False}))
        self.assertTrue(MV.child_directed({"id": "x", "kids": False, "episodes": [{"kids": True}]}))

    def test_deployed_kids_vmaps_reference_only_the_no_ad_tag(self):
        """web/ads/vmap is what deploy_web.sh ships: check the real files."""
        for t in KIDS:
            xml = (VMAP_DIR / f"{t['id']}.xml").read_text()
            found = tags(xml)
            self.assertTrue(found, t["id"])
            self.assertEqual(set(found), {MV.NO_AD_TAG}, f"{t['id']} is child-directed but its VMAP requests {found}")
            # Nothing else that looks like an ad server may hide in the file either.
            urls = set(re.findall(r"https?://[^\s\"'<>\]]+", xml)) - {"http://www.iab.net/videosuite/vmap"}
            self.assertEqual(urls, {MV.NO_AD_TAG}, t["id"])

    def test_kids_stay_ad_free_after_a_real_vast_tag_is_set(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(MV, "VAST_TAG", FAKE_GAM), mock.patch.object(MV, "OUT", pathlib.Path(tmp)):
            with contextlib.redirect_stdout(io.StringIO()):
                MV.main()
            out = pathlib.Path(tmp)
            for t in KIDS:
                found = tags((out / f"{t['id']}.xml").read_text())
                self.assertEqual(set(found), {MV.NO_AD_TAG}, f"{t['id']} would get real ads: {found}")
            # ...while ordinary titles do switch over (so this test isn't vacuous).
            adult = next(t for t in TITLES if not MV.child_directed(t))
            self.assertIn("doubleclick.net", (out / f"{adult['id']}.xml").read_text())

    def test_make_vmap_refuses_a_kids_schedule_with_ads(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(MV, "VAST_TAG", FAKE_GAM), mock.patch.object(MV, "OUT", pathlib.Path(tmp)), \
                mock.patch.object(MV, "schedule", lambda t, kind: MV.ad_break("start", "preroll", t["id"], kind)):
            with self.assertRaises(SystemExit):
                MV.main()

    def test_web_player_requests_no_ads_on_a_kids_profile(self):
        js = (ROOT / "web" / "watch" / "app.js").read_text()
        self.assertRegex(js, r"const onKidsProfile = \(\) => Boolean\(state\.profile\?\.is_kids\);")
        self.assertRegex(js, r"const adFree = t => onKidsProfile\(\) \|\| Boolean\(t\?\.kids\);")
        self.assertIn("&& !adFree(t)) startAds(t);", js)
        self.assertEqual(len(re.findall(r"(?<!function )\bstartAds\(", js)), 1,
                         "a new startAds call site must check adFree(t)")
        # IMA isn't even loaded for a Kids profile (the SDK sets identifiers on its own).
        calls = [m.start() for m in re.finditer(r"\bloadIma\(\)", js)]
        defs = js.index("function loadIma()")
        for i in calls:
            if i == defs + len("function "):
                continue
            self.assertIn("if (!onKidsProfile()) loadIma()", js[i - 25:i + 9], f"unguarded loadIma() at {i}")


if __name__ == "__main__":
    unittest.main()
