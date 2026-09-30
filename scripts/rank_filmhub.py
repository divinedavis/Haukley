"""Rank Filmhub's curated collections by popularity and pick the top 100 to license.

Popularity signal: IMDb vote count (title.ratings.tsv.gz, refreshed daily by IMDb).
Filmhub publishes no viewership numbers, so votes are the best public proxy for
how many people know and have watched a title.

Filters:
  - license type includes avod (Haukley is free, ad-supported)
  - IMDb rating >= 5.0 (drop hate-watch bait that tanks session time)
  - not already in scripts/catalog.json
  - not free to us already: published <= 1930 (US public domain as of 2026)
    or a well-documented US public-domain title (see PD_TITLES)
  - one row per IMDb id (Filmhub lists some films twice)

Collections refresh weekly, so rerun before each license swap:
  python3 scripts/rank_filmhub.py
Writes docs/content/filmhub-top100.csv and filmhub-all-ranked.csv.
"""
import csv, gzip, io, json, os, re, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTION = "https://filmhub.notion.site/api/v3/loadCachedPageChunkV2"
PAGE_ID = "af0f4263-b85a-4e25-af4c-f189ffe4fa59"
SHEET = ("https://docs.google.com/spreadsheets/d/e/2PACX-1vScChrdzAM8aH-1UdmjzwBr7q9bGfEyC3HBRiXJ_"
         "bU1vhZncBURzE25CJxmMTCnuKyt5RtroVNxY7ln/pub?output=csv&single=true&gid=")
RATINGS = "https://datasets.imdbws.com/title.ratings.tsv.gz"
MIN_RATING = 5.0
UA = {"user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"}
PD_TITLES = {  # US public domain (lapsed notice/renewal); don't spend a license on them
    "night of the living dead", "his girl friday", "scarlet street", "the stranger", "d.o.a.",
    "carnival of souls", "my man godfrey", "meet john doe", "house on haunted hill",
    "fear and desire", "and then there were none", "the man with the golden arm",
    "gulliver's travels", "scrooge", "the little shop of horrors",
}


def norm(t):
    t = re.split(r"[:：]", t.lower())[0].strip()
    return re.sub(r"[!.]$", "", t)


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA)).read()


def collections():
    body = json.dumps({"page": {"id": PAGE_ID}, "limit": 100, "cursor": {"stack": []},
                       "verticalColumns": False}).encode()
    req = urllib.request.Request(NOTION, body, {"content-type": "application/json", **UA})
    blocks = json.load(urllib.request.urlopen(req))["recordMap"]["block"]
    for b in blocks.values():
        v = b.get("value", {}); v = v.get("value", v)
        for seg in v.get("properties", {}).get("title", []):
            if len(seg) > 1 and seg[1][0][0] == "a" and "gid=" in seg[1][0][1]:
                yield seg[0].strip(), re.search(r"gid=(\d+)", seg[1][0][1]).group(1)


def main():
    titles = {}
    for name, gid in collections():
        rows = list(csv.reader(io.StringIO(get(SHEET + gid).decode())))
        hi = next((i for i, r in enumerate(rows) if "Title" in r), None)
        if hi is None:
            continue
        for r in rows[hi + 1:]:
            d = dict(zip(rows[hi], r))
            if not d.get("Title"):
                continue
            m = re.search(r"tt\d+", d.get("imdb", ""))
            key = m.group(0) if m else d["Link"]
            t = titles.setdefault(key, {**d, "imdb_id": m.group(0) if m else "", "collections": []})
            if name not in t["collections"]:
                t["collections"].append(name)

    ratings = {}
    with gzip.open(io.BytesIO(get(RATINGS)), "rt") as f:
        for line in f:
            tid, avg, votes = line.rstrip("\n").split("\t")
            ratings[tid] = (avg, votes)

    cat = json.load(open(os.path.join(ROOT, "scripts/catalog.json")))
    have = {norm(i["title"]) for k in ("movies", "shows") for i in cat[k]}

    ranked = []
    for t in titles.values():
        avg, votes = ratings.get(t["imdb_id"], ("", "0"))
        year = int(t["Year"]) if t["Year"].isdigit() else 0
        reason = ""
        if "avod" not in t["License Type"]:
            reason = "no AVOD license"
        elif norm(t["Title"]) in have:
            reason = "already on Haukley"
        elif (year and year <= 1930) or norm(t["Title"]) in PD_TITLES:
            reason = "US public domain (free)"
        elif avg and float(avg) < MIN_RATING:
            reason = f"IMDb rating under {MIN_RATING}"
        elif votes == "0":
            reason = "no IMDb votes"
        ranked.append({"title": t["Title"], "format": t["Format"], "year": t["Year"],
                       "genre": t["Genre"], "imdb_votes": int(votes), "imdb_rating": avg,
                       "license": t["License Type"], "collections": "; ".join(t["collections"]),
                       "filmhub_link": t["Link"], "imdb": t["imdb"], "excluded": reason})
    ranked.sort(key=lambda r: -r["imdb_votes"])

    out = os.path.join(ROOT, "docs/content")
    fields = list(ranked[0])
    with open(os.path.join(out, "filmhub-all-ranked.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fields); w.writeheader(); w.writerows(ranked)
    top = [r for r in ranked if not r["excluded"]][:100]
    with open(os.path.join(out, "filmhub-top100.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, ["rank"] + fields[:-1]); w.writeheader()
        for i, r in enumerate(top, 1):
            w.writerow({"rank": i, **{k: r[k] for k in fields[:-1]}})
    print(f"{len(ranked)} unique titles; top 100 votes range "
          f"{top[0]['imdb_votes']:,} -> {top[-1]['imdb_votes']:,}")


if __name__ == "__main__":
    main()
