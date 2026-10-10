"""Add the batch-3 films (scripts/free_titles_batch3.json) and the cleared U.S.-government /
CC documentaries and shorts in free_titles_series.json to catalog.json's "movies".

Like add_black_cinema.py: only entries that are live on the CDN and have a still are
written, so it can run while an ingest is still going. Rights, sources, trims and
advisories come from the research files; art direction and taglines live here. Run
make_posters.py / make_ios.py / make_web.py / make_roku.py / make_vmap.py /
make_roku_feed.py afterwards, like any catalog edit.

Usage: .venv/bin/python scripts/add_batch3.py
"""
import json
import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CDN = "https://haukley-media.nyc3.cdn.digitaloceanspaces.com/titles"
PD = "Public domain in the United States"
GOV = "U.S. government work — public domain in the United States"

# id -> (font, layout, tint, tagline)
STYLE = {
    "go-west": ("BebasNeue", "bottom", [35, 25, 10], "A drifter, a cow and a thousand steers."),
    "battling-butler": ("Anton", "bottom", [30, 20, 15], "He's not a boxer. He just plays one."),
    "topper-returns": ("PlayfairDisplay", "center", [20, 20, 35], "The victim wants her killer caught."),
    "made-for-each-other": ("PlayfairDisplay", "bottom", [30, 20, 25], "Married in a week. Tested for a lifetime."),
    "quicksand": ("Oswald", "bottom", [15, 15, 20], "Twenty dollars. One bad night. No way out."),
    "terror-by-night": ("Cinzel", "bottom", [20, 20, 25], "A diamond, a night train, a killer aboard."),
    "captain-kidd": ("Cinzel", "center", [30, 20, 10], "The King's pirate has his own plans."),
    "of-human-bondage": ("PlayfairDisplay", "bottom", [25, 20, 20], "The role that made Bette Davis a star."),
    "the-blue-angel": ("AbrilFatface", "center", [35, 15, 20], "Falling in love again, with Marlene Dietrich."),
    "nanook-of-the-north": ("Oswald", "top", [20, 25, 35], "A year at the edge of the Arctic."),
    "reefer-madness": ("Monoton", "center", [30, 30, 10], "The scare film that became a cult comedy."),
    "salt-of-the-earth": ("ArchivoBlack", "bottom", [30, 20, 10], "When the miners can't strike, their wives do."),
    "let-there-be-light": ("Oswald", "bottom", [20, 20, 25], "John Huston's long-suppressed film on war trauma."),
    "the-negro-soldier": ("Cinzel", "bottom", [25, 20, 15], "Black Americans in every war the nation fought."),
}
KIDS = {"go-west", "battling-butler"}
ADVISORY = {
    "let-there-be-light": "Real psychiatric patients describing wartime trauma.",
    "the-negro-soldier": "Depicts the segregated wartime Army; real combat footage.",
}


def live(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=15) as r:
            return r.status == 200
    except Exception:
        return False


def license_line(rights):
    if rights["basis"].startswith("cc-by"):
        return f"{rights['attribution']} · {rights['license_url']}"
    return GOV if rights["basis"] == "us-government-work" else PD


def main():
    films = json.loads((ROOT / "scripts" / "free_titles_batch3.json").read_text())
    films += [s for s in json.loads((ROOT / "scripts" / "free_titles_series.json").read_text())
              if s.get("kind") == "movie" and s["id"] in STYLE]
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
            "stream": stream, "kids": f["id"] in KIDS, "license": license_line(f["rights"]),
            "advisory": f.get("advisory") or ADVISORY.get(f["id"]),
            **({"silent": True} if f["year"] <= 1928 else {}),
        })
        added += 1
    cat["movies"] = movies
    cat_path.write_text(json.dumps(cat, indent=1, ensure_ascii=False) + "\n")
    print(f"{added} batch-3 films in the catalog")


if __name__ == "__main__":
    main()
