"""Write one VMAP ad schedule per title to web/ads/vmap/<id>.xml (served from haukley.com/ads/).

Schedule: a pre-roll at the start, plus one mid-roll at the halfway point for anything
20 minutes or longer. Every app points its ad tag at these files (scripts/ads.json), so
web, TV, iPhone and Roku break at the same places.

Until the Google Ad Manager account exists, every break points at NO_AD_TAG, an empty VAST
(the standard "no fill" answer): players skip the break and keep playing the film. Google's
public sample ad is NOT used any more: store reviewers treat visible test ads as an
unfinished app (App Review 2.2 rejected Crease for test-mode content). When the Ad Manager
tag exists, set VAST_TAG to it and rerun; no app update is needed. title_id rides along in
cust_params so the ad server can report revenue per film.

!!! COPPA: CHILD-DIRECTED TITLES NEVER GET ADS. !!!
Any title flagged `kids` in scripts/catalog.json (movies and shows; episodes play under their
show's id, so the show's flag covers every episode), any episode flagged `kids`, and any title
rated for children (TV-Y / TV-Y7) is written with NO_AD_TAG only - even after VAST_TAG is set.
Google Ad Manager tags serve personalized ads by default, and COPPA forbids collecting a
child's persistent identifiers for that. This file is the one server-side control that covers
every client (web, iPhone, tvOS, Fire TV, Roku, LG, Samsung) without an app update, so never
weaken child_directed() or route a kids title through VAST_TAG (not even with a
"tfcd=1"/non-personalized tag) without a legal review. main() refuses to finish if a kids
schedule references anything else, and tests/test_vmap_kids.py fails the push.

Usage: python3 scripts/make_vmap.py
"""
import json
import pathlib
import re
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "ads" / "vmap"
VAST_TAG = None  # Google Ad Manager VAST tag with a {cust} placeholder, once the account exists
NO_AD_TAG = "https://haukley.com/ads/no-ad.xml"
MIDROLL_MIN_MINUTES = 20
# Ratings that mean "made for children" (TV Parental Guidelines). G/PG/TV-G/TV-PG are general
# audience, not child-directed; those titles follow their `kids` flag.
CHILD_RATINGS = {"TV-Y", "TV-Y7", "TV-Y7-FV"}


def child_directed(t):
    """True for anything a child-directed audience watches: see the COPPA note at the top."""
    return bool(t.get("kids")) or t.get("rating") in CHILD_RATINGS or any(
        e.get("kids") or e.get("rating") in CHILD_RATINGS for e in t.get("episodes") or [])


def minutes(runtime):
    h = re.search(r"(\d+)\s*hr", runtime or "")
    m = re.search(r"(\d+)\s*min", runtime or "")
    return (int(h.group(1)) * 60 if h else 0) + (int(m.group(1)) if m else 0)


def hms(seconds):
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}.000"


def ad_break(offset, break_id, title_id, kind, kids=False):
    if kids or not VAST_TAG:
        tag = NO_AD_TAG  # COPPA: child-directed titles never reach the ad server
    else:
        cust = urllib.parse.quote(f"sample_ct=linear&title_id={title_id}&kind={kind}&break={break_id}", safe="")
        tag = VAST_TAG.format(cust=cust)
    return f"""  <vmap:AdBreak timeOffset="{offset}" breakType="linear" breakId="{break_id}">
    <vmap:AdSource id="{break_id}-ad" allowMultipleAds="false" followRedirects="true">
      <vmap:AdTagURI templateType="vast3"><![CDATA[{tag}]]></vmap:AdTagURI>
    </vmap:AdSource>
  </vmap:AdBreak>"""


def schedule(t, kind):
    kids = child_directed(t)
    breaks = [ad_break("start", "preroll", t["id"], kind, kids)]
    mins = minutes(t.get("runtime"))
    if kind == "movie" and mins >= MIDROLL_MIN_MINUTES and not kids:
        breaks.append(ad_break(hms(mins * 60 // 2), "midroll-1", t["id"], kind))
    # Kids schedules keep the exact shape every shipped client already parses (a no-fill
    # pre-roll), so no client changes behaviour; only the mid-roll request is dropped.
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<vmap:VMAP xmlns:vmap="http://www.iab.net/videosuite/vmap" version="1.0">\n'
            + "\n".join(breaks) + "\n</vmap:VMAP>\n")


def ad_tags(xml):
    return re.findall(r"<vmap:AdTagURI[^>]*><!\[CDATA\[(.*?)\]\]></vmap:AdTagURI>", xml, re.S)


def main():
    cat = json.loads((ROOT / "scripts" / "catalog.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.xml"):
        old.unlink()
    n = kids = 0
    for kind, key in (("movie", "movies"), ("show", "shows")):
        for t in cat[key]:
            xml = schedule(t, kind)
            if child_directed(t):
                tags = ad_tags(xml)
                if not tags or set(tags) != {NO_AD_TAG}:  # belt and braces: never ship this
                    raise SystemExit(f"COPPA: kids title {t['id']} would request {tags}")
                kids += 1
            (OUT / f"{t['id']}.xml").write_text(xml)
            n += 1
    print(f"{n} VMAP schedules -> {OUT} ({kids} child-directed, no ads)")


if __name__ == "__main__":
    main()
