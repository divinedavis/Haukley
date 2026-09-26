"""Bundle the catalog, art and ad config for the web app (web/watch/).

Same output as make_ios.py (catalog.json, ads.json, <id>/poster|card|backdrop|epN.jpg),
written to web/watch/catalog/ with a larger backdrop for desktop screens.

Usage: .venv/bin/python scripts/make_web.py
"""
import pathlib
import shutil

import make_ios

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "watch" / "catalog"

if __name__ == "__main__":
    shutil.rmtree(OUT, ignore_errors=True)
    make_ios.OUT = OUT
    make_ios.BACKDROP = (1600, 900)
    make_ios.main()
