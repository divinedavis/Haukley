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
    fonts = {t["id"]: t["font"] for key in ("movies", "shows") for t in cat[key]}
    out = json.loads((OUT / "catalog.json").read_text())
    for t in out["titles"]:
        t["font"] = fonts[t["id"]]
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
