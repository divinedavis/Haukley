"""Fire TV launcher icons are Haukley's, never the RN template's stock Android robot.

Amazon rejected Fire TV 1.4 (2026-10-11) for an icon resembling Google's Android mark.
Regenerate with scripts/make_android_icons.py. Stdlib only: size from the PNG header,
template icons by hash.
"""
from __future__ import annotations

import hashlib
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "android" / "app" / "src" / "main" / "res"
SIZES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
# sha256 of the react-native template's robot icons (ic_launcher + ic_launcher_round).
TEMPLATE_ROBOT = {
    "21304a0c9b00da6a72cfa31c7229c9528fc17b6e5eb4e68a969bce08c01a2fee",
    "ded7aabf6a56b694e486e096efd89e2f0c9067d292b634663898e352c9491f10",
    "520d05f978a15ba0ccf23006a1a5691a054a02478c70cafc5ebafae76e600f0d",
    "eef20f25fb1477d8c9df15757e764811cc503fb0777f18d0f7fb2d19178b5bf6",
    "2846e1a703e519791fe22f41bcb243b82f908d12e5ebcb43f020ddf9982780b0",
    "e77c5045bfdb6f4bbe955b3a793bfed3baa369ce4811ae2a9103d5480637cfff",
    "363a569beb72e8b007bf046454612148d4c9f782b9391352059fe83179f18e30",
    "eb3a34b13632e0cb3b1c0f4273035866cbe81b1b17b7178ce29d19c78d394a5e",
    "5bacd97a1b41e4413c6092cdbd83f65112a9124e823cfaa3a219c65e2761647b",
    "9ff27328b6916b7f75b99ef36153f154bb4724946e5654635cba2e257352c69f",
}


def _icons():
    for density, px in SIZES.items():
        for name in ("ic_launcher.png", "ic_launcher_round.png"):
            yield RES / f"mipmap-{density}" / name, px


def test_launcher_icons_are_not_the_android_robot():
    for path, _ in _icons():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest not in TEMPLATE_ROBOT, f"{path.relative_to(ROOT)} is the template Android robot"


def test_launcher_icon_sizes():
    for path, px in _icons():
        w, h = struct.unpack(">II", path.read_bytes()[16:24])
        assert (w, h) == (px, px), f"{path.relative_to(ROOT)} is {w}x{h}, want {px}x{px}"


def test_no_other_template_drawables_left():
    # Adaptive-icon XML would override the PNGs on newer Android and could point back at a robot.
    assert not list(RES.glob("mipmap-anydpi*")), "adaptive icon XML present; regenerate it from the Haukley icon"
