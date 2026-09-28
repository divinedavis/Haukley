"""Add the cleared films by Black directors (scripts/free_titles_black.json) to catalog.json.

Only entries without "skip" that are live on the CDN and have a still are written, so it
can run while an ingest is still going. Rights, sources, trims and advisories come from
the research file (docs/content/black-directors-research.md); the art direction and the
taglines live here. Run make_posters.py / make_ios.py / make_web.py / make_roku.py /
make_vmap.py / make_roku_feed.py afterwards, like any catalog edit.

Usage: .venv/bin/python scripts/add_black_cinema.py
"""
import json
import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CDN = "https://haukley-media.nyc3.cdn.digitaloceanspaces.com/titles"

STYLE = {
    "the-girl-from-chicago": ("Anton", "bottom", [30, 20, 10], "From Mississippi to the Harlem numbers racket."),
    "veiled-aristocrats": ("PlayfairDisplay", "center", [30, 25, 20], "A brother who passed for white comes home."),
    "murder-in-harlem": ("BebasNeue", "top", [15, 15, 25], "The wrong man, and the lawyer who won't quit."),
    "birthright-1938": ("Cinzel", "bottom", [25, 20, 15], "A Harvard man comes home to build a school."),
    "lying-lips": ("AbrilFatface", "center", [35, 15, 20], "Framed for murder. Two detectives believe her."),
    "the-blood-of-jesus": ("Cinzel", "center", [20, 15, 30], "Between Heaven and Hell, the city calls."),
    "go-down-death": ("PlayfairDisplay", "bottom", [15, 15, 25], "Inspired by James Weldon Johnson's poem."),
    "dirty-gertie-from-harlem-usa": ("Pacifico", "bottom", [35, 20, 20], "Harlem's hottest star heads for the islands."),
    "juke-joint": ("ArchivoBlack", "top", [35, 25, 10], "Two con men. One beauty contest. No money."),
    "souls-of-sin": ("Oswald", "bottom", [20, 20, 25], "Three roommates, one Harlem basement."),
}


def live(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=15) as r:
            return r.status == 200
    except Exception:
        return False


def main():
    films = json.loads((ROOT / "scripts" / "free_titles_black.json").read_text())
    cat_path = ROOT / "scripts" / "catalog.json"
    cat = json.loads(cat_path.read_text())
    ours = {f["id"] for f in films}
    movies = [m for m in cat["movies"] if m["id"] not in ours]  # rewrite ours in place
    added = 0
    for f in films:
        if f.get("skip") or f["id"] not in STYLE:
            continue
        stream = f"{CDN}/{f['id']}/master.m3u8"
        still = f"scripts/stills/{f['id']}.jpg"
        if not (ROOT / still).exists() or not live(stream):
            print(f"not live yet: {f['id']}")
            continue
        font, layout, tint, tagline = STYLE[f["id"]]
        movies.append({
            "id": f["id"], "title": f["title"], "still": still, "genre": f["genre"], "year": f["year"],
            "rating": f.get("rating", "NR"), "runtime": f["runtime"], "font": font, "layout": layout,
            "tint": tint, "tagline": tagline, "description": f["description"], "credits": f["credits"],
            "stream": stream, "kids": False, "license": "Public domain in the United States",
            "advisory": f.get("advisory"),
        })
        added += 1
    cat["movies"] = movies
    cat_path.write_text(json.dumps(cat, indent=1, ensure_ascii=False) + "\n")
    print(f"{added} films by Black directors in the catalog")


if __name__ == "__main__":
    main()
