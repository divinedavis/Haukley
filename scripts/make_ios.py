"""Bundle the catalog, art and ad config for the iPhone app (iphone/).

Reads scripts/catalog.json, scripts/rows.json and scripts/ads.json plus the art
from make_posters.py, and writes iphone/Haukley/Resources/Catalog/:
  catalog.json   titles, rows, episodes, streams, badges, hero colors
  ads.json       ad tag template + tracking endpoint (publishable key only)
  <id>/poster.jpg, card.jpg, backdrop.jpg, ep<N>.jpg

Usage: .venv/bin/python scripts/make_ios.py
"""
import colorsys
import json
import shutil
import pathlib

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
ART = ROOT / "src" / "assets" / "titles"
OUT = ROOT / "iphone" / "Haukley" / "Resources" / "Catalog"

POSTER = (400, 600)
CARD = (640, 360)
BACKDROP = (1280, 720)
STILL = (480, 270)


def save(src, dst, size, quality):
    dst.parent.mkdir(parents=True, exist_ok=True)
    Image.open(src).convert("RGB").resize(size, Image.LANCZOS).save(dst, quality=quality, optimize=True)


def stream_for(streams, tid, episode=0):
    # Same hash as streamFor() in src/catalog.ts and make_roku.py.
    h = episode
    for c in tid:
        h = (h * 31 + ord(c)) % 1000003
    return streams[h % len(streams)]


def hero_color(path):
    """A saturated, mid-bright version of the poster's average color for the Home gradient."""
    r, g, b = Image.open(path).convert("RGB").resize((1, 1), Image.LANCZOS).getpixel((0, 0))
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    r2, g2, b2 = colorsys.hls_to_rgb(h, 0.32, min(1.0, s * 1.6 + 0.15))
    return "#%02X%02X%02X" % (int(r2 * 255), int(g2 * 255), int(b2 * 255))


def badge_for(t, kind):
    if kind == "show" and t.get("seasons", 1) > 1:
        return "New Season"
    if t["year"] >= 2026:
        return "Recently Added"
    return None


def main():
    cat = json.loads((ROOT / "scripts" / "catalog.json").read_text())
    rows = json.loads((ROOT / "scripts" / "rows.json").read_text())
    ads = json.loads((ROOT / "scripts" / "ads.json").read_text())
    streams = rows["streams"]

    # Drop art for titles no longer in the catalog so removed titles don't ship in the bundle.
    keep = {t["id"] for key in ("movies", "shows") for t in cat[key]}
    for d in OUT.glob("*/"):
        if d.name not in keep:
            shutil.rmtree(d)

    titles = []
    for kind, key in (("movie", "movies"), ("show", "shows")):
        for t in cat[key]:
            tid = t["id"]
            src = ART / tid
            if not (src / "poster@2x.jpg").exists():
                continue  # art not generated yet (film still ingesting)
            save(src / "poster@2x.jpg", OUT / tid / "poster.jpg", POSTER, 82)
            save(src / "card@2x.jpg", OUT / tid / "card.jpg", CARD, 78)
            save(src / "backdrop@2x.jpg", OUT / tid / "backdrop.jpg", BACKDROP, 70)
            entry = {
                "id": tid, "kind": kind, "title": t["title"], "genre": t["genre"], "year": t["year"],
                "rating": t["rating"], "tagline": t["tagline"], "description": t["description"],
                "credits": t["credits"], "runtime": t.get("runtime"), "seasons": t.get("seasons"),
                "stream": t.get("stream") or stream_for(streams, tid), "badge": badge_for(t, kind),
                "heroColor": hero_color(src / "poster@2x.jpg"),
                "episodes": [],
            }
            if kind == "show":
                for i, name in enumerate(rows["episodeNames"], start=1):
                    save(src / f"ep{i}@2x.jpg", OUT / tid / f"ep{i}.jpg", STILL, 72)
                    entry["episodes"].append({
                        "number": i, "name": name, "minutes": 42 + (((i - 1) * 7 + len(tid)) % 14),
                        "summary": t["description"] if i == 1 else
                        f"The fallout from last week's discovery forces everyone in {t['title']} to choose a side.",
                        "stream": stream_for(streams, tid, i),
                    })
            titles.append(entry)

    out = {
        "titles": titles,
        "featured": rows["featured"],
        "upNext": rows["upNext"],
        "rows": rows["home"],
    }
    (OUT / "catalog.json").write_text(json.dumps(out, indent=1))
    (OUT / "ads.json").write_text(json.dumps(
        {k: ads[k] for k in ("adTagTemplate", "trackingUrl", "publishableKey")}, indent=1))
    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"{len(titles)} titles, {size / 1e6:.1f} MB -> {OUT}")


if __name__ == "__main__":
    main()
