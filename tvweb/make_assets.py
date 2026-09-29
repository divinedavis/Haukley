"""Icons, splash art and store images for the LG (webOS) and Samsung (Tizen) TV apps.

Package art (checked in, used by build.sh):
  tvweb/webos/icon.png 80x80, largeIcon.png 130x130, splash.png 1920x1080  (appinfo.json spec)
  tvweb/tizen/icon.png 512x423
Store art:
  marketing/lg/       icon-400x400.png, launcher-bg-1920x1080.png, splash-1920x1080.png,
                      screenshot-N-1280x720.png (from --shots)
  marketing/samsung/  icon-1920x1080.png (transparent RGBA, <=300 KB), icon-512x423.png (<=300 KB),
                      screenshot-N-1920x1080.jpg (<=500 KB, from --shots)
Sizes and limits are cited in tvweb/README.md.

Usage: .venv/bin/python tvweb/make_assets.py [--shots DIR_OF_1920x1080_PNGS]
"""
import argparse
import pathlib

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
ICON = ROOT / "marketing" / "firetv" / "icon-512.png"   # the same "H." mark as every other store
FONT = ROOT / "scripts" / "fonts" / "Montserrat.ttf"
ACCENT = (139, 108, 255)
# Screens for the store listings, in the order they should appear.
SHOTS = ["1-home", "2-rows", "3-detail", "9-episodes", "4-search", "6-player"]


def gradient(size, a=None, b=None):
    """Diagonal purple gradient sampled from the app icon's corners."""
    icon = Image.open(ICON).convert("RGB")
    a = a or icon.getpixel((4, 4))
    b = b or icon.getpixel((icon.width - 5, icon.height - 5))
    w, h = size
    small = Image.new("RGB", (64, 64))
    for y in range(64):
        for x in range(64):
            t = (x + y) / 126
            small.putpixel((x, y), tuple(int(p + (q - p) * t) for p, q in zip(a, b)))
    return small.resize(size, Image.BICUBIC)


def font(px):
    f = ImageFont.truetype(str(FONT), px)
    try:
        f.set_variation_by_name("ExtraBold")
    except Exception:
        pass
    return f


def wordmark(canvas, height_px, center):
    """'Haukley' in white with the purple period, centered at `center`."""
    d = ImageDraw.Draw(canvas)
    f = font(height_px)
    word, dot = "Haukley", "."
    wb = d.textbbox((0, 0), word, font=f)
    db = d.textbbox((0, 0), dot, font=f)
    total = (wb[2] - wb[0]) + (db[2] - db[0]) + height_px * 0.02
    x = center[0] - total / 2 - wb[0]
    y = center[1] - (wb[3] + wb[1]) / 2
    d.text((x, y), word, font=f, fill=(255, 255, 255, 255))
    d.text((x + (wb[2] - wb[0]) + height_px * 0.02 + wb[0] - db[0], y), dot, font=f, fill=ACCENT + (255,))


TILE = (0x2B, 0x1A, 0x55)  # appinfo.json iconColor


def square_icon(px):
    """The "H." mark on a flat TILE background. LG rejects gradient icon backgrounds and wants
    the icon background to match the tile color, so the store icon can't reuse the gradient one."""
    src = Image.open(ICON).convert("RGB").resize((1024, 1024), Image.LANCZOS)
    alpha = Image.new("L", src.size, 0)
    fg = Image.new("RGB", src.size, (255, 255, 255))
    spx, apx, fpx = src.load(), alpha.load(), fg.load()
    for y in range(src.height):
        for x in range(src.width):
            # The gradient never gets brighter than ~120 in any channel; the white H and the
            # purple dot both reach 255, so the brightest channel gives an anti-aliased mask.
            apx[x, y] = max(0, min(255, int((max(spx[x, y]) - 125) * 255 / 130)))
            if x > src.width * 0.65:  # the dot sits right of the H
                fpx[x, y] = ACCENT
    flat = Image.new("RGB", src.size, TILE)
    flat.paste(fg, (0, 0), alpha)
    return flat.resize((px, px), Image.LANCZOS)


def splash(size=(1920, 1080), tagline=True):
    img = gradient(size).convert("RGBA")
    wordmark(img, int(size[1] * 0.16), (size[0] / 2, size[1] * (0.45 if tagline else 0.5)))
    if tagline:
        d = ImageDraw.Draw(img)
        f = font(int(size[1] * 0.035))
        text = "Free movies. No sign-up."
        b = d.textbbox((0, 0), text, font=f)
        d.text(((size[0] - (b[2] - b[0])) / 2 - b[0], size[1] * 0.62), text, font=f, fill=(255, 255, 255, 200))
    return img.convert("RGB")


def save_under(img, path, limit_kb, fmt="PNG"):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "JPEG":
        for q in (90, 85, 80, 75, 70, 60):
            img.convert("RGB").save(path, "JPEG", quality=q, optimize=True)
            if path.stat().st_size <= limit_kb * 1000:
                return
    else:
        img.save(path, "PNG", optimize=True)
        if path.stat().st_size > limit_kb * 1000 and img.mode in ("RGB", "RGBA"):
            img.quantize(colors=256, method=Image.FASTOCTREE if img.mode == "RGBA" else Image.MEDIANCUT).save(path, "PNG", optimize=True)
    assert path.stat().st_size <= limit_kb * 1000, f"{path} is {path.stat().st_size} bytes"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", help="dir with 1920x1080 PNG screenshots named like SHOTS")
    a = ap.parse_args()

    webos, tizen = ROOT / "tvweb" / "webos", ROOT / "tvweb" / "tizen"
    lg, sam = ROOT / "marketing" / "lg", ROOT / "marketing" / "samsung"
    square_icon(80).save(webos / "icon.png", optimize=True)
    square_icon(130).save(webos / "largeIcon.png", optimize=True)
    splash().save(webos / "splash.png", optimize=True)

    icon_512x423 = gradient((512, 423))
    mark = Image.open(ICON).convert("RGB").resize((512, 512), Image.LANCZOS).crop((56, 100, 456, 412))   # the "H." with a little air around it
    mark_mask = Image.new("L", mark.size, 0)
    # Lift the white H and purple dot off the icon's own gradient.
    px, mpx = mark.load(), mark_mask.load()
    for y in range(mark.height):
        for x in range(mark.width):
            r, g, b = px[x, y]
            if (r > 200 and g > 200 and b > 200) or (r > 110 and b > 220 and g > 80):
                mpx[x, y] = 255
    icon_512x423.paste(mark, ((512 - mark.width) // 2, (423 - mark.height) // 2), mark_mask)
    icon_512x423.save(tizen / "icon.png", optimize=True)

    lg.mkdir(parents=True, exist_ok=True)
    save_under(square_icon(400), lg / "icon-400x400.png", 1000)
    save_under(gradient((1920, 1080)), lg / "launcher-bg-1920x1080.png", 2000)
    save_under(splash(), lg / "splash-1920x1080.png", 2000)

    # Samsung composes its home-row tile from this transparent logo over the background below.
    # The wordmark spans ~75% of the width so it reads as large as Netflix/YouTube tiles next to
    # it (at 230 px tall it covered ~55% and looked small, as on the Fire TV home row).
    transparent = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
    wordmark(transparent, 330, (960, 540))
    save_under(transparent, sam / "icon-1920x1080.png", 300)
    save_under(gradient((1920, 1080)), sam / "background-1920x1080.jpg", 300, "JPEG")
    save_under(icon_512x423, sam / "icon-512x423.png", 300)

    if a.shots:
        shots = pathlib.Path(a.shots)
        for i, name in enumerate(SHOTS, 1):
            src = shots / f"{name}.png"
            if not src.exists():
                continue
            img = Image.open(src).convert("RGB")
            assert img.size == (1920, 1080), f"{src} is {img.size}"
            save_under(img.resize((1280, 720), Image.LANCZOS), lg / f"screenshot-{i}-1280x720.png", 2000)
            if i <= 4:  # Samsung takes exactly 4
                save_under(img, sam / f"screenshot-{i}-1920x1080.jpg", 500, "JPEG")
    images = [q for q in [*lg.glob("*"), *sam.glob("*")] if q.suffix in (".png", ".jpg")]  # not the UX PDF
    for p in sorted([*webos.glob("*.png"), *tizen.glob("*.png"), *images]):
        with Image.open(p) as im:
            print(f"{p.relative_to(ROOT)}  {im.size[0]}x{im.size[1]} {im.mode}  {p.stat().st_size // 1000} KB")


if __name__ == "__main__":
    main()
