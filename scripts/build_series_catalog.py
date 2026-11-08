"""Write the cleared TV series from free_titles_series.json into catalog.json's "shows".

Only low-risk series are cleared (see docs/content/free-series-notes.md): no separately
renewed theme music, no protected character or trademark. A show that needs a content
advisory carries it in its "advisory" (shown on the title page and at play start). Each
show keeps only the episodes whose HLS stream is live on the CDN, so it can run while an
ingest is still going. Run make_posters.py / make_ios.py / make_web.py / make_roku.py /
make_vmap.py afterwards, like any catalog edit.

Usage: .venv/bin/python scripts/build_series_catalog.py
"""
import json
import pathlib
import re
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CDN = "https://haukley-media.nyc3.cdn.digitaloceanspaces.com/titles"

# Cleared shows, in row order, with the art and copy the catalog needs. "art" is the
# episode whose still becomes the show's key art; "kids" puts the show on Kids profiles.
CLEARED = {
    "apollo-mission-films": dict(
        title="Apollo: The Mission Films", art=4, font="Oswald", layout="bottom", tint=[10, 20, 40], kids=True,
        tagline="The Moon missions, in NASA's own films.",
        description="NASA's own films of the Apollo flights, from the first crewed test in Earth orbit "
                    "to the last lunar landing."),
    "sherlock-holmes-1954": dict(
        title="Sherlock Holmes", art=7, font="PlayfairDisplay", layout="bottom", tint=[30, 25, 15], kids=False,
        tagline="The game is afoot, every week."),
    # One Step Beyond is held back: "Alcoa Presents" bumpers and Alcoa Wrap credit cards
    # run through each episode (opening, act breaks, end credits), so it needs
    # frame-accurate multi-point cuts before it can air. Ingested e1-e2 stay unpublished.
    "rocky-jones-space-ranger": dict(
        title="Rocky Jones, Space Ranger", art=1, font="BebasNeue", layout="top", tint=[15, 20, 45], kids=True,
        tagline="Blast off with the Orbit Jet crew."),
    "life-with-elizabeth": dict(
        title="Life with Elizabeth", art=1, font="Pacifico", layout="bottom", tint=[35, 25, 25], kids=False,
        tagline="Aren't you ashamed, Elizabeth?"),
    "flip-the-frog-1930": dict(
        title="Flip the Frog", art=1, font="AbrilFatface", layout="center", tint=[30, 30, 20], kids=True,
        tagline="Ub Iwerks' first star, from 1930."),
    # U.S. government works (17 USC 105), added 2026-10-09. Wartime films: advisories required.
    "why-we-fight": dict(
        title="Why We Fight", art=4, font="Oswald", layout="bottom", tint=[30, 25, 15], kids=False,
        tagline="Frank Capra's wartime series for the U.S. Army.",
        advisory="Wartime propaganda with racist caricatures of Japanese people; real combat footage."),
    "wwii-combat-reports": dict(
        title="WWII Combat Reports", art=1, font="BebasNeue", layout="bottom", tint=[25, 25, 20], kids=False,
        tagline="Filmed under fire by the men who were there.",
        description="Official combat documentaries shot by U.S. service cameramen, from Midway and "
                    "Tarawa to Iwo Jima, including John Ford's and John Huston's war films.",
        advisory="Real combat footage, including the dead and wounded."),
    "caminandes": dict(
        title="Caminandes", art=2, font="Pacifico", layout="top", tint=[20, 30, 20], kids=True,
        tagline="One llama. Many obstacles."),
    "blender-open-shorts": dict(
        title="Blender Open Shorts", art=6, font="Montserrat", layout="center", tint=[25, 15, 40], kids=True,
        tagline="Animated shorts from Blender Studio."),
}

GOV = "U.S. government work — public domain in the United States"
PD = "Public domain in the United States"


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
    series = {s["id"]: s for s in json.loads((ROOT / "scripts" / "free_titles_series.json").read_text())}
    cat_path = ROOT / "scripts" / "catalog.json"
    cat = json.loads(cat_path.read_text())
    shows = []
    for sid, cfg in CLEARED.items():
        s = series[sid]
        eps = []
        for e in s["episodes"]:
            if e.get("skip"):
                continue
            stream = f"{CDN}/{sid}/e{e['number']}/master.m3u8"
            still = f"scripts/stills/{sid}/e{e['number']}.jpg"
            if not (ROOT / still).exists() or not live(stream):
                continue
            eps.append({
                "number": len(eps) + 1,
                "season": e.get("season", 1),
                # Research labels like "Episode 3 (archive misc. no. 4)" are for us, not viewers.
                "name": re.sub(r"\s*\(archive[^)]*\)", "", e["name"]),
                "minutes": e["minutes"],
                "summary": e["summary"],
                "stream": stream,
                "still": still,
            })
        if not eps:
            print(f"skip {sid}: no live episodes yet")
            continue
        art = next((x for x in eps if x["still"].endswith(f"/e{cfg['art']}.jpg")), eps[0])
        shows.append({
            "id": sid, "title": cfg["title"], "still": art["still"], "genre": s["genre"],
            "year": s["year"], "rating": s.get("rating", "NR"),
            "seasons": len({x["season"] for x in eps}),
            "font": cfg["font"], "layout": cfg["layout"], "tint": cfg["tint"],
            "tagline": cfg["tagline"], "description": cfg.get("description", s["description"]), "credits": s["credits"],
            "kids": cfg["kids"], "license": license_line(s["rights"]),
            **({"advisory": cfg["advisory"]} if cfg.get("advisory") else {}),
            "episodes": eps,
        })
        print(f"{sid}: {len(eps)}/{len(s['episodes'])} episodes live")
    cat["shows"] = shows
    cat_path.write_text(json.dumps(cat, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(shows)} shows -> {cat_path}")


if __name__ == "__main__":
    main()
