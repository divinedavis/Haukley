"""Bundle the catalog, art, ad config and title fonts for the web app (web/watch/).

Same output as make_ios.py (catalog.json, ads.json, <id>/poster|card|backdrop|epN.jpg),
written to web/watch/catalog/ with a larger backdrop for desktop screens. Each title also
gets its poster font (scripts/fonts, OFL) so the web hero can set the title like key art;
fonts are subset to Latin and saved as woff2 in web/watch/fonts/.

Usage: .venv/bin/python scripts/make_web.py   (needs fonttools + brotli in .venv)
"""
import json
import pathlib
import shutil

from fontTools import subset

import make_ios

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "watch" / "catalog"

if __name__ == "__main__":
    shutil.rmtree(OUT, ignore_errors=True)
    make_ios.OUT = OUT
    make_ios.BACKDROP = (1600, 900)
    make_ios.main()

    cat = json.loads((ROOT / "scripts" / "catalog.json").read_text())
    src = {t["id"]: t for key in ("movies", "shows", "live") for t in cat.get(key, [])}
    fonts = {i: t["font"] for i, t in src.items()}
    out = json.loads((OUT / "catalog.json").read_text())
    # Only publish titles whose stream is actually on the CDN (the rest are still ingesting).
    import urllib.request
    def live(url):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=15) as r:
                return r.status == 200
        except Exception:
            return False
    out["titles"] = [t for t in out["titles"] if live(t["stream"])]
    ids = {t["id"] for t in out["titles"]}
    out["featured"] = [i for i in out["featured"] if i in ids]
    print("live on CDN:", len(ids))
    for t in out["titles"]:
        s = src[t["id"]]
        t["font"] = s["font"]
        for k in ("kids", "license", "silent", "advisory"):  # web-only extras
            if s.get(k):
                t[k] = s[k]
    (OUT / "catalog.json").write_text(json.dumps(out, indent=1))

    fdir = ROOT / "web" / "watch" / "fonts"
    shutil.rmtree(fdir, ignore_errors=True)
    fdir.mkdir(parents=True)
    for name in sorted(set(fonts.values())):
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = ["*"]
        f = subset.load_font(str(ROOT / "scripts" / "fonts" / f"{name}.ttf"), opts)
        sub = subset.Subsetter(opts)
        sub.populate(unicodes=list(range(0x20, 0x7F)) + [0xA0, 0xB7, 0xE9, 0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2026])
        sub.subset(f)
        subset.save_font(f, str(fdir / f"{name}.woff2"), opts)
    shutil.copy(ROOT / "scripts" / "fonts" / "LICENSE.md", fdir / "LICENSE.md")
    print("fonts:", ", ".join(f"{p.stem} {p.stat().st_size // 1024}K" for p in sorted(fdir.glob("*.woff2"))))
