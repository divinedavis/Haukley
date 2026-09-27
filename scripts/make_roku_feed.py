"""Roku Search feed for Haukley (so Roku search / voice can find and deep link titles).

Writes web/roku/search-feed.json plus the public artwork it points at
(web/img/feed/<id>-*.jpg), and validates the feed against Roku's published JSON
schema (scripts/roku/search-feed.schema.json, saved from developer.roku.com).

Asset ids and playIds are the same ids the Roku app's deep linking accepts:
"<titleId>" for movies and series, "<titleId>-e<N>" for episodes.

Only titles whose stream is live on the CDN are included (the rest are still
ingesting). Register the feed URL (https://haukley.com/roku/search-feed.json) in the
Roku dashboard under Search feeds.

Usage: .venv/bin/python scripts/make_roku_feed.py
"""
import json
import pathlib
import re
import shutil
import urllib.request

import jsonschema
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
ART = ROOT / "src" / "assets" / "titles"
WEB = ROOT / "web"
BASE_URL = "https://haukley.com"

GENRES = {
    "War": ["war"], "Documentary": ["documentary"], "Animation": ["animated"], "Fantasy": ["fantasy"],
    "Western": ["western"], "Noir": ["crime", "thriller"],
    "Thriller": ["thriller"], "Drama": ["drama"], "Action": ["action"], "Adventure": ["adventure"],
    "Mystery": ["mystery"], "Horror": ["horror"], "Sci-Fi": ["science fiction"], "Comedy": ["comedy"],
    "Period Drama": ["drama", "historical drama"], "Crime": ["crime"], "Heist": ["crime", "action"],
    "Romance": ["romance"], "Crime Drama": ["crime drama"], "Docuseries": ["documentary"],
    "Political Drama": ["drama", "politics"], "Travel": ["travel"],
}


def text(value):
    return [{"value": value, "languages": ["en"]}]


def seconds(runtime):
    h = re.search(r"(\d+)\s*hr", runtime or "")
    m = re.search(r"(\d+)\s*min", runtime or "")
    return (int(h.group(1)) if h else 0) * 3600 + (int(m.group(1)) if m else 0) * 60


def image(src, name, size, tid):
    out = WEB / "img" / "feed" / f"{tid}-{name}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.open(src).convert("RGB").resize(size, Image.LANCZOS).save(out, quality=82, optimize=True)
    return f"{BASE_URL}/img/feed/{out.name}"


def rating(kind, value):
    return [{"source": "USA_PR" if kind == "show" else "MPAA", "value": value}]


def credits(line):
    """'Directed by A · B · Starring C · D' -> Roku credit objects with roles."""
    out, role = [], "actor"
    for part in (p.strip() for p in line.split("·")):
        for prefix, r in (("Directed by", "director"), ("Starring", "actor"), ("Narrated by", "narrator"),
                          ("Produced by", "producer"), ("Music by", "composer"), ("Edited by", "editor"),
                          ("With", "actor")):
            if part.startswith(prefix + " "):
                role, part = r, part[len(prefix):].strip()
                break
        if part and role in ("actor", "director", "narrator", "producer"):  # skip editors, composers
            out.append({"name": part, "role": role})
    return out


def live(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=15) as r:
            return r.status == 200
    except Exception:
        return False


def main():
    cat = json.loads((ROOT / "scripts" / "catalog.json").read_text())
    rows = json.loads((ROOT / "scripts" / "rows.json").read_text())
    schema = json.loads((ROOT / "scripts" / "roku" / "search-feed.schema.json").read_text())
    allowed = set(schema["definitions"]["genre_type"]["enum"])
    series = json.loads((ROOT / "scripts" / "free_titles_series.json").read_text())
    heights = {t["id"]: t["source"].get("height", 480)
               for t in json.loads((ROOT / "scripts" / "free_titles.json").read_text())}
    shutil.rmtree(WEB / "img" / "feed", ignore_errors=True)

    assets = []
    for kind, key in (("movie", "movies"), ("show", "shows")):
        for t in cat[key]:
            tid = t["id"]
            src = ART / tid
            if not (src / "poster@2x.jpg").exists() or (t.get("stream") and not live(t["stream"])):
                continue  # still ingesting
            quality = "hd" if heights.get(tid, 480) >= 720 else "sd"
            genres = [g for g in GENRES.get(t["genre"], ["drama"]) if g in allowed] or ["drama"]
            common = {
                "titles": text(t["title"]),
                "shortDescriptions": text(t["tagline"][:200]),
                "longDescriptions": text(t["description"][:500]),
                "releaseDate": f"{t['year']}-01-01",
                "genres": genres,
                "credits": credits(t["credits"]),
                "advisoryRatings": rating(kind, t["rating"]),
                "images": [
                    {"type": "main", "url": image(src / "poster@2x.jpg", "poster", (600, 900), tid)},
                    {"type": "background", "url": image(src / "backdrop@2x.jpg", "background", (1280, 720), tid)},
                ],
            }
            if kind == "movie":
                assets.append({"id": tid, "type": "movie", **common,
                               "durationInSeconds": seconds(t.get("runtime")),
                               "content": {"playOptions": [{"license": "free", "quality": quality, "playId": tid}]}})
                continue
            assets.append({"id": tid, "type": "series", **common})
            src_eps = {e["number"]: e for x in series if x["id"] == tid for e in x["episodes"]}
            for e in t["episodes"]:
                i = e["number"]
                eid = f"{tid}-e{i}"
                height = src_eps.get(i, {}).get("source", {}).get("height", 480)
                assets.append({
                    "id": eid, "type": "episode",
                    "titles": text(e["name"]),
                    "shortDescriptions": text(e["summary"][:200]),
                    "releaseDate": f"{t['year']}-01-01",
                    "genres": genres,
                    "advisoryRatings": rating(kind, t["rating"]),
                    "images": [{"type": "main",
                                "url": image(src / f"ep{i}@2x.jpg", f"e{i}", (640, 360), tid)}],
                    "episodeInfo": {"seriesId": tid, "seasonNumber": e.get("season", 1), "episodeNumber": i},
                    "durationInSeconds": e["minutes"] * 60,
                    "content": {"playOptions": [{"license": "free", "quality": "hd" if height >= 720 else "sd",
                                                 "playId": eid}]},
                })

    feed = {"version": "1", "defaultLanguage": "en", "defaultAvailabilityCountries": ["us"], "assets": assets}
    jsonschema.validate(feed, schema)
    out = WEB / "roku" / "search-feed.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(feed, indent=1))
    kinds = {}
    for a in assets:
        kinds[a["type"]] = kinds.get(a["type"], 0) + 1
    print(f"valid against Roku schema: {len(assets)} assets {kinds} -> {out}")


if __name__ == "__main__":
    main()
