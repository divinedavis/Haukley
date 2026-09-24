"""Splash art for the iPhone launch: HAUKLEY hidden in a maze of silver lines.

The effect (maze resolving into a word inside a framed bar) follows the owner's
reference clip; the lettering and maze are our own. Two transparent layers:
  SplashMaze.png     maze segments + frame rules (the part that recedes)
  SplashLetters.png  engraved silver letterforms (the part that emerges)
Prints the purple period's position as fractions of the image for SplashView.

Usage: .venv/bin/python scripts/make_splash.py
"""
import json
import pathlib
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "iphone" / "Haukley" / "Resources" / "Assets.xcassets"
FONT = ROOT / "scripts" / "fonts" / "LeagueGothic.ttf"

W, H = 1500, 420          # 3x of a 500x140pt bar
BAND_TOP, BAND_BOT = 70, 360
STROKE = 11               # line weight shared by maze and letter channels
CELL = 34                 # maze grid


def silver(size, top=(236, 238, 242), bottom=(150, 156, 166)):
    w, h = size
    g = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / (h - 1)
        g.putpixel((0, y), tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    return g.resize(size)


def letters_mask():
    """HAUKLEY in a condensed face, stretched wide so the letters fill the band edge to edge."""
    f = ImageFont.truetype(str(FONT), 400)
    text = "HAUKLEY"
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    bbox = probe.textbbox((0, 0), text, font=f)
    word = Image.new("L", (bbox[2] - bbox[0] + 20, bbox[3] - bbox[1] + 20), 0)
    ImageDraw.Draw(word).text((10 - bbox[0], 10 - bbox[1]), text, font=f, fill=255)
    word = word.crop(word.getbbox())
    band_h = BAND_BOT - BAND_TOP - 36
    target_w = W - 180 - 60          # leave room on the right for the purple period
    word = word.resize((target_w, band_h), Image.LANCZOS)
    m = Image.new("L", (W, H), 0)
    left, top = 70, BAND_TOP + 18
    m.paste(word, (left, top))
    return m.point(lambda v: 255 if v > 110 else 0), left + target_w, top + band_h


def engraved(mask):
    """Silver fill with a dark channel running inside each stroke."""
    inner = mask.filter(ImageFilter.MinFilter(STROKE * 2 + 1))
    channel = ImageChops.subtract(inner, inner.filter(ImageFilter.MinFilter(7)))
    fill = silver((W, H))
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.paste(fill, (0, 0), mask)
    dark = Image.new("RGBA", (W, H), (18, 16, 26, 255))
    out.paste(dark, (0, 0), channel)
    return out


def maze(avoid, seed=11):
    """A perfect labyrinth (depth-first) on a grid over the band; walls stop at the letters."""
    rnd = random.Random(seed)
    x0, y0 = 30, BAND_TOP + 6
    cols, rows = (W - 60) // CELL, (BAND_BOT - BAND_TOP - 12) // CELL
    keep_out = avoid.filter(ImageFilter.MaxFilter(STROKE + 8))  # odd size: PIL requires it

    # Carve passages.
    seen = [[False] * rows for _ in range(cols)]
    open_walls = set()
    stack = [(0, 0)]
    seen[0][0] = True
    while stack:
        cx, cy = stack[-1]
        nbrs = [(cx + dx, cy + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if 0 <= cx + dx < cols and 0 <= cy + dy < rows and not seen[cx + dx][cy + dy]]
        if not nbrs:
            stack.pop()
            continue
        nx, ny = rnd.choice(nbrs)
        open_walls.add(frozenset(((cx, cy), (nx, ny))))
        seen[nx][ny] = True
        stack.append((nx, ny))

    walls = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(walls)
    for cx in range(cols):
        for cy in range(rows):
            px, py = x0 + cx * CELL, y0 + cy * CELL
            # Right wall and bottom wall of each cell, unless carved open.
            if cx + 1 < cols and frozenset(((cx, cy), (cx + 1, cy))) not in open_walls:
                d.line([(px + CELL, py), (px + CELL, py + CELL)], fill=255, width=STROKE)
            if cy + 1 < rows and frozenset(((cx, cy), (cx, cy + 1))) not in open_walls:
                d.line([(px, py + CELL), (px + CELL, py + CELL)], fill=255, width=STROKE)
    # The letters sit in the maze: cut walls where they'd cross a glyph.
    walls = ImageChops.subtract(walls, keep_out)
    d = ImageDraw.Draw(walls)
    # Frame: a heavy rule on top and a thin one under the band, as in the reference.
    d.rectangle([20, BAND_TOP - 30, W - 20, BAND_TOP - 12], fill=255)
    d.rectangle([20, BAND_BOT + 12, W - 20, BAND_BOT + 18], fill=255)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.paste(silver((W, H), (200, 204, 214), (110, 116, 128)), (0, 0), walls)
    return out


def imageset(name, img):
    folder = ASSETS / f"{name}.imageset"
    folder.mkdir(parents=True, exist_ok=True)
    img.save(folder / f"{name}.png")
    (folder / "Contents.json").write_text(json.dumps(
        {"images": [{"filename": f"{name}.png", "idiom": "universal", "scale": "3x"}],
         "info": {"author": "xcode", "version": 1}}))


def main():
    mask, text_right, baseline = letters_mask()
    imageset("SplashLetters", engraved(mask))
    imageset("SplashMaze", maze(mask))
    r = 24
    cx, cy = text_right + 12 + r, baseline - r
    print(f"size {W}x{H}  dotX={cx / W:.4f} dotY={cy / H:.4f} dotR={r / W:.4f}")


if __name__ == "__main__":
    main()
