#!/usr/bin/env python3
"""Fire TV / Android TV launcher icons from the Haukley app icon (the iPhone 1024 px "H.").

    .venv/bin/python scripts/make_android_icons.py

Writes mipmap-*/ic_launcher.png (square) and ic_launcher_round.png (circle-masked) at every
density. The RN template's stock Android robot icons got Fire TV 1.4 rejected by Amazon
(10/11, IP policy: "device icon that resembles ... Google, Android"); tests/test_android_icons.py
keeps them out.
"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "iphone/Haukley/Resources/Assets.xcassets/AppIcon.appiconset/icon-1024.png"
RES = ROOT / "android/app/src/main/res"
SIZES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}


def main():
    src = Image.open(SRC).convert("RGBA")
    for density, px in SIZES.items():
        out = RES / f"mipmap-{density}"
        icon = src.resize((px, px), Image.LANCZOS)
        icon.save(out / "ic_launcher.png", optimize=True)
        # Draw the circle mask 4x and shrink it for a smooth edge.
        mask = Image.new("L", (px * 4, px * 4), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, px * 4 - 1, px * 4 - 1), fill=255)
        round_icon = icon.copy()
        round_icon.putalpha(mask.resize((px, px), Image.LANCZOS))
        round_icon.save(out / "ic_launcher_round.png", optimize=True)
        print(f"{density}: {px}px")


if __name__ == "__main__":
    main()
