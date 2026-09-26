"""Write one VMAP ad schedule per title to web/ads/vmap/<id>.xml (served from haukley.com/ads/).

Schedule: a pre-roll at the start, plus one mid-roll at the halfway point for anything
20 minutes or longer. Every app points its ad tag at these files (scripts/ads.json), so
web, TV, iPhone and Roku break at the same places.

Each break's VAST tag is Google's public sample linear ad until the Google Ad Manager
account exists; then only VAST_TAG changes. title_id rides along in cust_params so the ad
server can report revenue per film.

Usage: python3 scripts/make_vmap.py
"""
import json
import pathlib
import re
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "ads" / "vmap"
VAST_TAG = ("https://pubads.g.doubleclick.net/gampad/ads?iu=/21775744923/external/single_ad_samples"
            "&sz=640x480&cust_params={cust}&ciu_szs=300x250%2C728x90&gdfp_req=1&output=vast"
            "&unviewed_position_start=1&env=vp&impl=s&correlator=")
MIDROLL_MIN_MINUTES = 20


def minutes(runtime):
    h = re.search(r"(\d+)\s*hr", runtime or "")
    m = re.search(r"(\d+)\s*min", runtime or "")
    return (int(h.group(1)) * 60 if h else 0) + (int(m.group(1)) if m else 0)


def hms(seconds):
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}.000"


def ad_break(offset, break_id, title_id, kind):
    cust = urllib.parse.quote(f"sample_ct=linear&title_id={title_id}&kind={kind}&break={break_id}", safe="")
    tag = VAST_TAG.format(cust=cust)
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
