"""The App Store creative-asset copy follows Apple's Asset Library rules.

scripts/make_creative_assets.py needs Pillow, so this reads its PAGES taglines with ast
(stdlib only) and checks them against the words App Review has rejected Haukley for
(asc_listing.PRICE_WORDS / THIRD_PARTY) plus the Asset Library bans: URLs, (c), other
platforms or stores. Rendering itself is checked by eye, not here (~30 s per run).
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "make_creative_assets.py"
LISTING = ROOT / "iphone" / "scripts" / "asc_listing.py"
BANNED = ("http", "www.", ".com", "©", "(c)", "netflix", "roku", "fire tv", "prime video",
          "google play", "amazon", "#1", "best", "award")


def _assign(path: Path, name: str):
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return node.value
    raise AssertionError(f"{name} not found in {path.name}")


def _taglines() -> dict[str, str]:
    pages = _assign(SCRIPT, "PAGES")
    return {k.value: v.elts[1].value for k, v in zip(pages.keys, pages.values)}


def test_pages_cover_default_and_two_cpps():
    pages = _taglines()
    assert "default" in pages
    assert len([p for p in pages if p.startswith("cpp-")]) >= 2


def test_taglines_are_short_and_clean():
    price = ast.literal_eval(_assign(LISTING, "PRICE_WORDS"))
    third = ast.literal_eval(_assign(LISTING, "THIRD_PARTY"))
    for page, text in _taglines().items():
        low = text.lower()
        assert len(text) <= 45, f"{page}: tagline is {len(text)} chars"
        for w in (*price, *third, *BANNED):
            assert w not in low, f"{page}: tagline contains {w!r}"


def test_canvases_are_apples_sizes():
    sizes = ast.literal_eval(_assign(SCRIPT, "CANVASES"))
    assert sizes == {"header": (3840, 1646), "search": (3840, 2560), "universal": (5244, 2950)}
