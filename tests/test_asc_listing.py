"""The App Store listing text passes the checks App Review has rejected us for.

tvOS 1.0 (3) was rejected 2026-10-02 under 2.3.7 ("Free" in the subtitle) and 4.1(a)
(Big Buck Bunny in the screenshots/description). Stdlib only: the ASC client modules
(jwt, requests) are stubbed, since only the listing constants and lint() are under test.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "iphone" / "scripts" / "asc_listing.py"


def _load():
    stubs = {"requests": types.ModuleType("requests"), "asc": types.ModuleType("asc")}
    for name in ("api", "load_config", "make_token"):
        setattr(stubs["asc"], name, None)
    saved = {k: sys.modules.get(k) for k in stubs}
    sys.modules.update(stubs)
    try:
        spec = importlib.util.spec_from_file_location("asc_listing", SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def test_listing_lint_is_clean():
    assert _load().lint() == []


def test_lint_catches_price_and_third_party():
    mod = _load()
    mod.SUBTITLE = "Free classic movies"
    mod.DESCRIPTION = {"TV_OS": "Animated open movies — Big Buck Bunny"}
    errs = mod.lint()
    assert any("'free'" in e and "subtitle" in e for e in errs), errs
    assert any("big buck bunny" in e for e in errs), errs
