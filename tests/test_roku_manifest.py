"""Roku manifest rules that brs-node (the emulator in run_fast.sh) doesn't enforce but a real
Roku does. 2026-10-10: the first install on a real Streaming Stick failed "Compilation Failed
... PlayerTask ... Roku_Ads.brs" because the manifest never declared the RAF library."""
import pathlib
import re

ROKU = pathlib.Path(__file__).resolve().parent.parent / "roku"
MANIFEST = dict(l.split("=", 1) for l in (ROKU / "manifest").read_text().splitlines() if "=" in l and not l.startswith("#"))


def test_raf_library_declared_when_used():
    uses_raf = any('Library "Roku_Ads.brs"' in p.read_text() for p in (ROKU / "components").glob("*.brs"))
    if uses_raf:
        assert "roku_ads_lib" in MANIFEST.get("bs_libs_required", ""), "manifest needs bs_libs_required=roku_ads_lib"


def test_version_fields_are_numbers():
    for k in ("major_version", "minor_version", "build_version"):
        assert re.fullmatch(r"\d+", MANIFEST.get(k, "")), f"manifest {k} must be a number"
