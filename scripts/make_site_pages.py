"""Build the crawlable catalog pages of haukley.com from the web catalog.

Writes, from web/watch/catalog/catalog.json (make_web.py output) + the rights files:
  web/films/index.html             every title, grouped by the app's rows
  web/films/<id>/index.html        one page per movie / show (synopsis, credits, episodes,
                                   why it's free to watch, more like it, JSON-LD)
  web/collections/<key>/index.html one page per app row, with its curator's note
  web/index.html                   the block between <!-- rows:start --> / <!-- rows:end -->
  web/sitemap.xml, web/robots.txt
The /watch player stays the place to watch; every page links into it (#/title/<id>).
Usage: python3 scripts/make_site_pages.py   (tests/test_site_pages.py fails if stale)
"""
import html
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
SRC = WEB / "_src"
SITE = "https://haukley.com"
RIGHTS_FILES = ["free_titles.json", "free_titles_batch2.json", "free_titles_batch3.json",
                "free_titles_black.json", "free_titles_series.json"]
SKIP_ROWS = {"live", "new", "quick"}  # not collections: live TV, a date window, a runtime cut
HOME_ROWS = ["picks", "black-cinema", "silent-comedy", "horror", "tv-shows"]

# Curator's note for each collection page (keyed by the app row's key).
NOTES = {
    "picks": "Our ten favorites from the library: the films we'd put on first for a friend who "
             "thinks old movies are slow. Fritz Lang's Metropolis and F. W. Murnau's Nosferatu "
             "still shape how science fiction and horror look a century later; Buster Keaton's "
             "The General and Harold Lloyd's Safety Last! are stunt comedy nobody has topped; "
             "and His Girl Friday talks faster than most films made since.",
    "tv-shows": "Series from the early days of television and from public agencies: NASA's own "
                "Apollo mission films, the 1954 Sherlock Holmes series, Betty White in Life with "
                "Elizabeth, the space serial Rocky Jones, Ub Iwerks's Flip the Frog cartoons, "
                "and Frank Capra's Why We Fight films made for the U.S. Army. Pick up any "
                "episode wherever you like.",
    "black-cinema": "Before Hollywood would cast Black actors as anything but servants, Black "
                    "filmmakers built a parallel industry of \"race films\" made for Black "
                    "audiences. Oscar Micheaux wrote, produced and directed more than forty "
                    "features, and Spencer Williams's The Blood of Jesus was the first race film "
                    "added to the National Film Registry. Some of these films show attitudes of "
                    "their time; titles that need it carry a content note.",
    "silent-comedy": "Buster Keaton and Harold Lloyd did their own stunts, built their gags "
                     "around real trains, boats, clocks and collapsing houses, and worked out "
                     "timing that comedians still study. With no dialogue to date them, these "
                     "films still play to kids and adults alike.",
    "horror": "Where screen horror comes from: German Expressionism's shadows, Lon Chaney's "
              "makeup, Bela Lugosi and Boris Karloff, and the low-budget independents of the "
              "1950s and '60s, including Roger Corman and a young Francis Ford Coppola. Night of "
              "the Living Dead fell into the public domain on release because its prints went "
              "out without a copyright notice, which is why it is free here.",
    "noir": "Detectives, drifters and doomed bargains, shot in hard light and deep shadow. "
            "Fritz Lang, Orson Welles and Ida Lupino are here, alongside the lean B-movies of "
            "the late 1940s and '50s and an early Alfred Hitchcock thriller.",
    "swash": "Swords, sails and stunt work from the years when Douglas Fairbanks set the "
             "template for every action hero since, plus the stop-motion dinosaurs of The Lost "
             "World (1925) and Charles Laughton as Captain Kidd.",
    "scifi": "Rockets, robots and dreams, from Georges Méliès's 1902 trip to the Moon and Fritz "
             "Lang's Metropolis to the open-source animated films of the Blender studio. The "
             "oldest and newest titles on Haukley sit side by side here.",
    "screwball": "Screwball comedies, romances and dramas from the studio era: Cary Grant, "
                 "Clara Bow, the Marx Brothers, Carole Lombard, Joan Crawford, Bette Davis and "
                 "Marlene Dietrich, and Murnau's Sunrise, one of the most beautiful silent "
                 "films ever made.",
    "war": "World War I as Hollywood filmed it, including Wings (the first Best Picture "
           "winner), Howard Hughes's Hell's Angels, The Big Parade and All Quiet on the Western "
           "Front, plus two documentaries made for the U.S. Army: The Negro Soldier and John "
           "Huston's Let There Be Light.",
    "westerns": "Trails, cattle drives and showdowns, including John Wayne's first starring "
                "role in The Big Trail (1930), shot in an early widescreen process, and Errol "
                "Flynn in Santa Fe Trail.",
    "shorts": "Short animated films from the Blender studio in Amsterdam, made with free "
              "software and released under Creative Commons licenses so anyone can watch and "
              "share them. Most run under fifteen minutes.",
    "history": "Films that changed what movies could do: the first trip to the Moon on film, "
               "Nanook of the North, Man with a Movie Camera, the first Best Picture winner, "
               "and Salt of the Earth, made by blacklisted filmmakers in 1954. If you're "
               "starting a film education, start here.",
}

ADVISORY_LABEL = "Content note"


def esc(s):
    return html.escape(str(s or ""), quote=True)


def rights_sources():
    """id -> Wikipedia URL from the rights research (shown as 'Learn more')."""
    out = {}
    for name in RIGHTS_FILES:
        p = ROOT / "scripts" / name
        if not p.exists():
            continue
        for t in json.loads(p.read_text()):
            for url in (t.get("rights") or {}).get("sources") or []:
                if "wikipedia.org/wiki/" in url:
                    out.setdefault(t["id"], url)
    return out


def why_free(t):
    lic = t.get("license") or ""
    if lic.startswith("U.S. government work"):
        return ("This film was made by the U.S. government. Works made by federal employees as "
                "part of their jobs have no copyright in the United States, so anyone may show it.")
    if "creativecommons.org" in lic or "Creative Commons" in lic or "CC BY" in lic:
        url = re.search(r"https://creativecommons\.org/licenses/[^ ]+", lic)
        credit = lic.split(" · ")[0]
        link = f' (<a href="{esc(url.group(0))}">license</a>)' if url else ""
        return (f"Its makers released it under a Creative Commons Attribution license{link}, "
                f"which lets anyone share it as long as they credit them: {esc(credit)}.")
    year = t.get("year") or 0
    if year and year <= 1930:
        return (f"It was published in {year}. In the United States, films published in 1930 or "
                "earlier are now in the public domain, so they belong to everyone.")
    return ("It is in the public domain in the United States: its copyright was never renewed "
            "or it was published without a copyright notice, so it belongs to everyone. "
            "Haukley streams it in the U.S. only.")


def head(title, desc, path, extra=""):
    h = (SRC / "head.inc").read_text()
    h = h.replace("__TITLE__", esc(title)).replace("__DESC__", esc(desc)).replace("__PATH__", path)
    return h.replace("</head>", extra + "</head>") if extra else h


def foot():
    return (SRC / "foot.inc").read_text() + "</body>\n</html>\n"


def poster(t, eager=False):
    lazy = "" if eager else ' loading="lazy"'
    return (f'<a class="tile" href="/films/{esc(t["id"])}/"><img src="/watch/catalog/{esc(t["id"])}/poster.jpg"'
            f' alt="{esc(t["title"])}" width="200" height="300"{lazy}><span>{esc(t["title"])}</span></a>')


def meta_line(t):
    bits = [str(t["year"]) if t.get("year") else "", t.get("genre"),
            t.get("runtime") or (f'{len(t["episodes"])} episodes' if t.get("episodes") else ""),
            t.get("rating")]
    if t.get("silent"):
        bits.append("Silent")
    return " · ".join(esc(b) for b in bits if b)


def jsonld(t):
    kind = "TVSeries" if t["kind"] == "show" else "Movie"
    d = {"@context": "https://schema.org", "@type": kind, "name": t["title"],
         "description": t.get("description"), "genre": t.get("genre"),
         "url": f'{SITE}/films/{t["id"]}/', "image": f'{SITE}/watch/catalog/{t["id"]}/poster.jpg',
         "isAccessibleForFree": True}
    if t.get("year"):
        d["dateCreated"] = str(t["year"])
    m = re.match(r"Directed by ([^·]+)", t.get("credits") or "")
    if m and kind == "Movie":
        d["director"] = {"@type": "Person", "name": m.group(1).strip()}
    if t.get("episodes"):
        d["numberOfEpisodes"] = len(t["episodes"])
    body = json.dumps(d, ensure_ascii=False).replace("</", "<\\/")
    return f'  <script type="application/ld+json">{body}</script>\n'


def title_page(t, rows_of, by_id, sources):
    tid = t["id"]
    desc = t.get("description") or ""
    kind = "series" if t["kind"] == "show" else "film"
    seo_title = f'{t["title"]} ({t["year"]}): watch free on Haukley' if t.get("year") else f'{t["title"]}: watch free on Haukley'
    out = [head(seo_title, desc, f"/films/{tid}/", jsonld(t)), '  <main class="title-page">\n    <div class="wrap">\n']
    out.append('      <p class="crumbs"><a href="/films/">All films &amp; shows</a>')
    if rows_of.get(tid):
        r = rows_of[tid][0]
        out.append(f' / <a href="/collections/{esc(r["key"])}/">{esc(r["title"])}</a>')
    out.append("</p>\n      <div class=\"title-top\">\n")
    out.append(f'        <img class="title-poster" src="/watch/catalog/{esc(tid)}/poster.jpg" alt="{esc(t["title"])} poster" width="300" height="450">\n')
    out.append("        <div>\n")
    out.append(f'          <h1>{esc(t["title"])}</h1>\n          <p class="title-meta">{meta_line(t)}</p>\n')
    if t.get("tagline"):
        out.append(f'          <p class="tagline">{esc(t["tagline"])}</p>\n')
    out.append(f'          <p class="lede">{esc(desc)}</p>\n')
    if t.get("credits"):
        out.append(f'          <p class="credits">{esc(t["credits"])}</p>\n')
    out.append(f'          <p class="hero-watch"><a class="btn btn-primary" href="/watch/#/title/{esc(tid)}">Watch free</a></p>\n')
    if t.get("advisory"):
        out.append(f'          <p class="advisory"><b>{ADVISORY_LABEL}:</b> {esc(t["advisory"])}</p>\n')
    out.append("        </div>\n      </div>\n")
    if t.get("episodes"):
        out.append(f'      <h2 class="sub">Episodes</h2>\n      <ol class="episodes">\n')
        for e in t["episodes"]:
            mins = f' <span class="muted">· {e["minutes"]} min</span>' if e.get("minutes") else ""
            out.append(f'        <li><b>{esc(e.get("name"))}</b>{mins}<p>{esc(e.get("summary"))}</p></li>\n')
        out.append("      </ol>\n")
    out.append(f'      <h2 class="sub">Why this {kind} is free to watch</h2>\n      <p class="muted body">{why_free(t)}</p>\n')
    if t.get("silent"):
        out.append('      <p class="muted body">It is a silent film: the story is told in pictures and title cards. '
                   'Haukley plays it as it was released, so some copies have a music track and some play in silence.</p>\n')
    if sources.get(tid):
        out.append(f'      <p class="muted body">Learn more about it on <a href="{esc(sources[tid])}" rel="nofollow">Wikipedia</a>.</p>\n')
    more = []
    for r in rows_of.get(tid, []):
        more += [i for i in r["ids"] if i != tid and i in by_id and i not in more]
    if not more:
        more = [x["id"] for x in by_id.values() if x["genre"] == t["genre"] and x["id"] != tid]
    if more:
        out.append('      <h2 class="sub">More like this</h2>\n      <div class="tiles">\n')
        out += ["        " + poster(by_id[i]) + "\n" for i in more[:12]]
        out.append("      </div>\n")
    out.append("    </div>\n  </main>\n")
    return "".join(out) + foot()


def collection_page(r, by_id):
    note = NOTES.get(r["key"], "")
    out = [head(f'{r["title"]}: free on Haukley', note[:155] or r["title"], f'/collections/{r["key"]}/'),
           '  <main class="title-page">\n    <div class="wrap">\n',
           '      <p class="crumbs"><a href="/films/">All films &amp; shows</a></p>\n',
           f'      <h1>{esc(r["title"])}</h1>\n']
    if note:
        out.append(f'      <p class="lede">{esc(note)}</p>\n')
    out.append('      <div class="list">\n')
    for i in r["ids"]:
        if i not in by_id:
            continue
        t = by_id[i]
        out.append(f'        <article>{poster(t)}<div><h2><a href="/films/{esc(i)}/">{esc(t["title"])}</a></h2>'
                   f'<p class="title-meta">{meta_line(t)}</p><p class="muted">{esc(t.get("description"))}</p></div></article>\n')
    out.append("      </div>\n    </div>\n  </main>\n")
    return "".join(out) + foot()


def index_page(rows, by_id):
    desc = (f"All {len(by_id)} films and shows on Haukley: silent comedy, film noir, classic horror, "
            "Pioneers of Black Cinema, NASA documentaries and more. Free to watch in the U.S.")
    out = [head("Free classic movies and shows: the full Haukley library", desc, "/films/"),
           '  <main class="title-page">\n    <div class="wrap">\n',
           '      <h1>The Haukley library</h1>\n',
           f'      <p class="lede">{esc(desc)} Every title has been checked by hand: we research the '
           'copyright of each film before it goes up, and we tell you on its page why it is free.</p>\n']
    seen = set()
    for r in rows:
        ids = [i for i in r["ids"] if i in by_id]
        seen.update(ids)
        out.append(f'      <h2 class="sub"><a href="/collections/{esc(r["key"])}/">{esc(r["title"])}</a></h2>\n      <div class="tiles">\n')
        out += ["        " + poster(by_id[i]) + "\n" for i in ids]
        out.append("      </div>\n")
    rest = sorted((t for i, t in by_id.items() if i not in seen), key=lambda t: t["title"])
    if rest:
        out.append('      <h2 class="sub">More films</h2>\n      <div class="tiles">\n')
        out += ["        " + poster(t) + "\n" for t in rest]
        out.append("      </div>\n")
    out.append('      <h2 class="sub">A to Z</h2>\n      <ul class="az">\n')
    for t in sorted(by_id.values(), key=lambda t: re.sub(r"^(The|A|An) ", "", t["title"])):
        out.append(f'        <li><a href="/films/{esc(t["id"])}/">{esc(t["title"])}</a> <span class="muted">{esc(t.get("year"))}</span></li>\n')
    out.append("      </ul>\n    </div>\n  </main>\n")
    return "".join(out) + foot()


def home_rows(rows, by_id):
    out = ['<!-- rows:start (scripts/make_site_pages.py) -->\n', '        <div class="rows">\n']
    for key in HOME_ROWS:
        r = next((x for x in rows if x["key"] == key), None)
        if not r:
            continue
        out.append(f'          <div class="row"><h3><a href="/collections/{esc(key)}/">{esc(r["title"])}</a></h3><div class="strip">\n')
        out += ["            " + poster(by_id[i]) + "\n" for i in r["ids"][:10] if i in by_id]
        out.append("          </div></div>\n")
    out.append("        </div>\n        <!-- rows:end -->")
    return "".join(out)


def build():
    cat = json.loads((WEB / "watch" / "catalog" / "catalog.json").read_text())
    by_id = {t["id"]: t for t in cat["titles"] if t["kind"] in ("movie", "show")}
    rows = [r for r in cat["rows"] if r["key"] not in SKIP_ROWS and r.get("ids")]
    rows_of = {}
    for r in rows:
        for i in r["ids"]:
            rows_of.setdefault(i, []).append(r)
    sources = rights_sources()
    files = {"films/index.html": index_page(rows, by_id)}
    for t in by_id.values():
        files[f'films/{t["id"]}/index.html'] = title_page(t, rows_of, by_id, sources)
    for r in rows:
        files[f'collections/{r["key"]}/index.html'] = collection_page(r, by_id)
    home = (WEB / "index.html").read_text()
    files["index.html"] = re.sub(r"<!-- rows:start.*?<!-- rows:end -->", lambda _: home_rows(rows, by_id), home, flags=re.S)
    urls = ["/", "/films/", "/about/", "/filmmakers/", "/support/", "/contact/", "/privacy/", "/terms/"]
    urls += [f"/collections/{r['key']}/" for r in rows] + [f"/films/{i}/" for i in by_id]
    files["sitemap.xml"] = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                            + "".join(f"  <url><loc>{SITE}{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    files["robots.txt"] = f"User-agent: *\nDisallow: /ads/\nDisallow: /api/\n\nSitemap: {SITE}/sitemap.xml\n"
    return files


if __name__ == "__main__":
    import shutil
    for d in ("films", "collections"):
        shutil.rmtree(WEB / d, ignore_errors=True)
    for rel, text in build().items():
        p = WEB / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    print(f"wrote {len(build())} files")
