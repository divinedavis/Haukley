"""Roku manifest rules that brs-node (the emulator in run_fast.sh) doesn't enforce but a real
Roku does. 2026-10-10: the first install on a real Streaming Stick failed "Compilation Failed
... PlayerTask ... Roku_Ads.brs" because the manifest never declared the RAF library."""
import pathlib
import re

ROKU = pathlib.Path(__file__).resolve().parent.parent / "roku"
def _code(p):
    """BrightScript source minus comment lines (comments may name the RAF library)."""
    return "\n".join(l for l in p.read_text().splitlines() if not l.lstrip().startswith("'"))


MANIFEST = dict(l.split("=", 1) for l in (ROKU / "manifest").read_text().splitlines() if "=" in l and not l.startswith("#"))


def test_raf_library_declared_when_used():
    uses_raf = any('Library "Roku_Ads.brs"' in _code(p) for p in (ROKU / "components").glob("*.brs"))
    if uses_raf:
        assert "roku_ads_lib" in MANIFEST.get("bs_libs_required", ""), "manifest needs bs_libs_required=roku_ads_lib"


def test_version_fields_are_numbers():
    for k in ("major_version", "minor_version", "build_version"):
        assert re.fullmatch(r"\d+", MANIFEST.get(k, "")), f"manifest {k} must be a number"


def test_no_raf_while_listing_is_non_monetized():
    # 2026-10-11: the Roku listing is set to no monetization (Partner Payouts enrollment page is
    # broken), so the app must not render ads. Delete this test when ads come back on Roku.
    for p in (ROKU / "components").glob("*.brs"):
        src = _code(p)
        assert 'Library "Roku_Ads.brs"' not in src and "Roku_Ads()" not in src, f"{p.name} still uses RAF"
    assert "roku_ads_lib" not in MANIFEST.get("bs_libs_required", "")
