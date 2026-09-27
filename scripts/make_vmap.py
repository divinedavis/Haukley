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


def minutes(runtime):
    h = re.search(r"(\d+)\s*hr", runtime or "")
    m = re.search(r"(\d+)\s*min", runtime or "")
    return (int(h.group(1)) * 60 if h else 0) + (int(m.group(1)) if m else 0)


def hms(seconds):
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}.000"


def ad_break(offset, break_id, title_id, kind):
    cust = urllib.parse.quote(f"sample_ct=linear&title_id={title_id}&kind={kind}&break={break_id}", safe="")
    tag = VAST_TAG.format(cust=cust) if VAST_TAG else NO_AD_TAG
    return f"""  <vmap:AdBreak timeOffset="{offset}" breakType="linear" breakId="{break_id}">
    <vmap:AdSource id="{break_id}-ad" allowMultipleAds="false" followRedirects="true">
      <vmap:AdTagURI templateType="vast3"><![CDATA[{tag}]]></vmap:AdTagURI>
    </vmap:AdSource>
  </vmap:AdBreak>"""


def main():
    cat = json.loads((ROOT / "scripts" / "catalog.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.xml"):
        old.unlink()
    n = 0
    for kind, key in (("movie", "movies"), ("show", "shows")):
        for t in cat[key]:
            breaks = [ad_break("start", "preroll", t["id"], kind)]
            mins = minutes(t.get("runtime"))
            if kind == "movie" and mins >= MIDROLL_MIN_MINUTES:
                breaks.append(ad_break(hms(mins * 60 // 2), "midroll-1", t["id"], kind))
            xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                   '<vmap:VMAP xmlns:vmap="http://www.iab.net/videosuite/vmap" version="1.0">\n'
                   + "\n".join(breaks) + "\n</vmap:VMAP>\n")
            (OUT / f"{t['id']}.xml").write_text(xml)
            n += 1
    print(f"{n} VMAP schedules -> {OUT}")


if __name__ == "__main__":
    main()
