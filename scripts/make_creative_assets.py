#!/usr/bin/env python3
"""App Store creative assets (Asset Library, fall 2026) for Haukley.

Apple's three canvases:

    header    3840x1646  product page header (and each custom product page's)
    search    3840x2560  search results slot
    universal 5244x2950  16:9 master Apple can crop into either

Brand only: the near-black launch field (#0D0A14) with the icon's violet glow, the
"Haukley." wordmark (Montserrat ExtraBold + violet dot, as in Wordmark.png), and
abstract poster tiles / TV / film-strip shapes. No film stills: even public-domain
frames invite 4.1 questions, and a horror still would fight the 4+ rating. No price
words either ("free" got the 2026-10-02 tvOS build rejected under 2.3.7), no URLs, no (c).

Everything that must be read sits inside the centre 60% x 70% of each canvas, since
Apple crops the edges per device; the outer tiles are decoration and may be cut.

Pages:
    default            main product page (header + search + universal)
    cpp-appletv        Apple TV viewers: the tvOS home screen as shapes inside a TV
    cpp-silent-comedy  the "Silent Comedy Legends" row: an intertitle card + film strips

Usage: ~/.venvs/spendcap/bin/python scripts/make_creative_assets.py [OUT_DIR]
"""
from __future__ import annotations

import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, "scripts", "fonts")
CANVASES = {"header": (3840, 1646), "search": (3840, 2560), "universal": (5244, 2950)}

BG = (13, 10, 20)            # LaunchBackground colorset
VIOLET = (139, 108, 255)     # #8B6CFF, brand colour in asc-pinterest.json
DEEP = (85, 51, 204)         # the icon's gradient top-left
WHITE = (255, 255, 255)
SOFT = (206, 198, 236)
CREAM = (238, 226, 198)
SEPIA = [(58, 50, 44), (82, 70, 58), (104, 92, 78), (70, 66, 72), (46, 42, 52), (92, 84, 96)]


def font(name: str, size: float, weight: str | None = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(os.path.join(FONTS, name), max(8, int(size)))
    if weight:
        f.set_variation_by_name(weight)
    return f


# ---------- backgrounds ----------

def field(w: int, h: int, glow=(0.5, 0.42), seed: int = 7) -> Image.Image:
    """Near-black field, a big soft violet glow, a second deep one, light grain."""
    img = Image.new("RGB", (w, h), BG)
    small = Image.new("RGB", (w // 8, h // 8), BG)
    d = ImageDraw.Draw(small)
    sw, sh = small.size
    for (fx, fy, rx, ry, col, a) in ((glow[0], glow[1], 0.55, 0.85, DEEP, 0.85),
                                      (glow[0] + 0.22, glow[1] + 0.35, 0.35, 0.6, (60, 30, 140), 0.6)):
        for i in range(40, 0, -1):
            t = i / 40
            c = tuple(int(BG[k] + (col[k] - BG[k]) * a * (1 - t) ** 1.6) for k in range(3))
            d.ellipse([(fx - rx * t) * sw, (fy - ry * t) * sh, (fx + rx * t) * sw, (fy + ry * t) * sh], fill=c)
    img = small.filter(ImageFilter.GaussianBlur(sw / 30)).resize((w, h), Image.BICUBIC)
    # vignette
    vig = Image.new("L", (w // 8, h // 8), 0)
    ImageDraw.Draw(vig).ellipse([-sw * 0.15, -sh * 0.25, sw * 1.15, sh * 1.25], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(sw / 10)).resize((w, h), Image.BICUBIC)
    img = Image.composite(img, Image.new("RGB", (w, h), (6, 5, 10)), vig)
    random.seed(seed)
    noise = Image.effect_noise((w // 2, h // 2), 18).resize((w, h)).convert("RGB")
    return Image.blend(img, noise, 0.035)


def shadow(base: Image.Image, box, radius: float, blur: float, alpha: int = 150, off=(0, 0)) -> None:
    sh = Image.new("RGBA", base.size, (0, 0, 0, 0))
    x0, y0, x1, y1 = box
    ImageDraw.Draw(sh).rounded_rectangle([x0 + off[0], y0 + off[1], x1 + off[0], y1 + off[1]],
                                         radius, fill=(0, 0, 0, alpha))
    base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))


# ---------- pieces ----------

def poster(w: int, h: int, rng: random.Random, tint=None) -> Image.Image:
    """An abstract classic-film poster: toned gradient, a soft 'spotlight', title bars."""
    top = tint or rng.choice(SEPIA)
    bot = tuple(max(0, c // 3) for c in top)
    p = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(p)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)], fill=tuple(int(top[k] * (1 - t) + bot[k] * t) for k in range(3)))
    spot = Image.new("L", (w, h), 0)
    cx, cy = rng.uniform(0.3, 0.7) * w, rng.uniform(0.2, 0.45) * h
    ImageDraw.Draw(spot).ellipse([cx - w * 0.42, cy - w * 0.42, cx + w * 0.42, cy + w * 0.42], fill=120)
    spot = spot.filter(ImageFilter.GaussianBlur(w * 0.18))
    p = Image.composite(Image.new("RGB", (w, h), tuple(min(255, c + 90) for c in top)), p, spot)
    d = ImageDraw.Draw(p)
    # "title" bars: bottom-centred, top-centred or one big block, like old one-sheets
    style = rng.choice(("bottom", "bottom", "top", "block"))
    if style == "block":
        bw, bh = w * rng.uniform(0.62, 0.8), h * 0.13
        y0 = h * rng.uniform(0.62, 0.7)
        d.rounded_rectangle([(w - bw) / 2, y0, (w + bw) / 2, y0 + bh], h * 0.02, fill=(236, 228, 214))
        d.rounded_rectangle([(w - bw * 0.5) / 2, y0 + bh + h * 0.04, (w + bw * 0.5) / 2, y0 + bh + h * 0.065],
                            h * 0.012, fill=(170, 160, 150))
        return p
    y = h * (0.70 if style == "bottom" else 0.09)
    for i, frac in enumerate((rng.uniform(0.55, 0.78), rng.uniform(0.38, 0.6))):
        bw, bh = w * frac, h * (0.055 if i == 0 else 0.032)
        d.rounded_rectangle([(w - bw) / 2, y, (w + bw) / 2, y + bh], bh / 2,
                            fill=(236, 228, 214) if i == 0 else (170, 160, 150))
        y += bh + h * 0.03
    return p


def paste_round(base: Image.Image, im: Image.Image, xy, radius: float, opacity: float = 1.0,
                shadow_blur: float = 0.0) -> None:
    x, y = int(xy[0]), int(xy[1])
    if shadow_blur:
        shadow(base, (x, y, x + im.width, y + im.height), radius, shadow_blur, 170, (0, shadow_blur * 0.5))
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius, fill=int(255 * opacity))
    base.paste(im.convert("RGBA"), (x, y), mask)


def tile_wall(base: Image.Image, cx: float, cy: float, s: float, side: int, rng: random.Random,
              cols: int = 3, rows: int = 3) -> None:
    """A tilted, staggered wall of poster tiles that fades toward the canvas edge."""
    tw, th = int(300 * s), int(440 * s)
    gap = int(40 * s)
    W = cols * tw + (cols - 1) * gap
    H = rows * th + (rows - 1) * gap + th
    layer = Image.new("RGBA", (W + 2 * gap, H + 2 * gap), (0, 0, 0, 0))
    for c in range(cols):
        off = (c * th * 0.38) % th - th * 0.5
        for r in range(rows + 1):
            tint = VIOLET if rng.random() < 0.12 else None
            pim = poster(tw, th, rng, tint=(78, 60, 150) if tint else None)
            paste_round(layer, pim, (gap + c * (tw + gap), gap + off + r * (th + gap)), 26 * s)
    layer = layer.rotate(-9 * side, resample=Image.BICUBIC, expand=True)
    # fade: strongest toward the centre of the canvas, gone at the outer edge
    fade = Image.new("L", layer.size, 0)
    fd = ImageDraw.Draw(fade)
    for x in range(layer.width):
        t = x / layer.width if side < 0 else 1 - x / layer.width
        fd.line([(x, 0), (x, layer.height)], fill=int(255 * min(1, 0.15 + t * 1.25) * 0.9))
    a = layer.getchannel("A")
    layer.putalpha(Image.composite(a, Image.new("L", a.size, 0), fade))
    base.alpha_composite(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)))


def wordmark(base: Image.Image, cx: float, cy: float, size: float, glow: bool = True) -> tuple:
    """'Haukley' + violet dot, centred on (cx, cy). Returns its bbox."""
    f = font("Montserrat.ttf", size, "ExtraBold")
    d = ImageDraw.Draw(base)
    text = "Haukley"
    l, t, r, b = d.textbbox((0, 0), text, font=f)
    dot = size * 0.17
    gapd = size * 0.07
    tw = r - l + gapd + dot
    x = cx - tw / 2 - l
    y = cy - (b - t) / 2 - t
    if glow:
        g = Image.new("RGBA", base.size, (0, 0, 0, 0))
        ImageDraw.Draw(g).text((x, y), text, font=f, fill=(110, 80, 255, 150))
        base.alpha_composite(g.filter(ImageFilter.GaussianBlur(size * 0.12)))
    d = ImageDraw.Draw(base)
    d.text((x, y), text, font=f, fill=WHITE)
    dx = x + r + gapd
    base_y = y + f.getmetrics()[0]  # text drawn at y sits on y + ascent
    d.ellipse([dx, base_y - dot, dx + dot, base_y], fill=VIOLET)
    return (cx - tw / 2, y + t, cx + tw / 2, y + b)


def centred_text(base, text, cx, y, f, fill, max_w=None):
    d = ImageDraw.Draw(base)
    size = f.size
    while max_w and d.textlength(text, font=f) > max_w:
        size -= 2
        f = f.font_variant(size=size)
    w = d.textlength(text, font=f)
    d.text((cx - w / 2, y), text, font=f, fill=fill)
    return f


def play_pill(base, cx, cy, s, label="Play"):
    f = font("Montserrat.ttf", 46 * s, "Bold")
    d = ImageDraw.Draw(base)
    tw = d.textlength(label, font=f)
    w, h = tw + 170 * s, 112 * s
    box = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    shadow(base, box, h / 2, 30 * s, 160, (0, 14 * s))
    d.rounded_rectangle(box, h / 2, fill=WHITE)
    tx = box[0] + 62 * s
    tri = 34 * s
    d.polygon([(tx, cy - tri / 2), (tx, cy + tri / 2), (tx + tri * 0.9, cy)], fill=BG)
    asc, desc = f.getmetrics()
    d.text((tx + tri * 0.9 + 22 * s, cy - (asc + desc) / 2 + 2 * s), label, font=f, fill=BG)


def dot(base, cx, cy, r, col=VIOLET, blur=0):
    lay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(lay).ellipse([cx - r, cy - r, cx + r, cy + r], fill=col + (255,))
    if blur:
        lay = lay.filter(ImageFilter.GaussianBlur(blur))
    base.alpha_composite(lay)


# ---------- pages ----------

def render_default(w: int, h: int, tagline: str) -> Image.Image:
    s = min(h / 1646, w / 3840) * (1.0 if w / h > 2 else 1.12)
    base = field(w, h).convert("RGBA")
    rng = random.Random(11)
    # tiles scale with the narrower dimension so they never crowd the centre
    ts = 0.95 * min(h / 1646, w / 3840 * 1.25)
    rows = math.ceil(h / (480 * ts)) + 1
    cxl = min(0.13 * w, 0.25 * w - 560 * ts)
    tile_wall(base, cxl, h * 0.5, ts, -1, rng, rows=rows)
    tile_wall(base, w - cxl, h * 0.5, ts, 1, rng, rows=rows)
    # dark core so the wordmark always reads over the tiles
    core = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(core).ellipse([w * 0.27, h * 0.18, w * 0.73, h * 0.82], fill=BG + (200,))
    base.alpha_composite(core.filter(ImageFilter.GaussianBlur(w * 0.05)))
    bb = wordmark(base, w / 2, h * 0.40, 330 * s)
    f = font("Montserrat.ttf", 104 * s, "SemiBold")
    centred_text(base, tagline, w / 2, bb[3] + 60 * s, f, SOFT, w * 0.5)
    play_pill(base, w / 2, bb[3] + 330 * s, s * 1.3)
    dot(base, w * 0.335, h * 0.24, 22 * s)
    dot(base, w * 0.68, h * 0.76, 14 * s, (200, 188, 255))
    return base.convert("RGB")


def tv_ui(w: int, h: int, s: float, rng: random.Random) -> Image.Image:
    """The tvOS home screen as shapes: hero, nav pill, Play/Details, a row of posters."""
    ui = field(w, h, glow=(0.72, 0.3), seed=3)
    d = ImageDraw.Draw(ui)
    # hero art: a soft toned panel on the right
    hero = poster(int(w * 0.62), int(h * 0.66), rng, tint=(96, 80, 150))
    hero = hero.crop((0, 0, hero.width, int(hero.height * 0.62))).resize((int(w * 0.62), int(h * 0.66)))
    m = Image.new("L", hero.size, 0)
    md = ImageDraw.Draw(m)
    for x in range(hero.width):
        md.line([(x, 0), (x, hero.height)], fill=int(255 * min(1, x / (hero.width * 0.55))))
    ui.paste(hero, (w - hero.width, 0), m)
    ui = ui.convert("RGBA")
    # top nav
    wordmark(ui, w * 0.1, h * 0.07, h * 0.055, glow=False)
    nav = (w * 0.42, h * 0.035, w * 0.58, h * 0.105)
    ov = Image.new("RGBA", ui.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.rounded_rectangle(nav, (nav[3] - nav[1]) / 2, fill=(255, 255, 255, 34))
    od.rounded_rectangle((nav[0] + 8 * s, nav[1] + 8 * s, w * 0.5, nav[3] - 8 * s), 30 * s, fill=(255, 255, 255, 70))
    od.rounded_rectangle((w * 0.523, h * 0.062, w * 0.557, h * 0.078), 6 * s, fill=(255, 255, 255, 90))
    od.rounded_rectangle((w * 0.443, h * 0.062, w * 0.477, h * 0.078), 6 * s, fill=(255, 255, 255, 230))
    ui.alpha_composite(ov)
    d = ImageDraw.Draw(ui)
    # hero text bars
    x0 = w * 0.05
    d.rounded_rectangle((x0, h * 0.25, x0 + w * 0.12, h * 0.268), 6 * s, fill=(190, 182, 210))
    d.rounded_rectangle((x0, h * 0.3, x0 + w * 0.3, h * 0.375), 14 * s, fill=WHITE)
    d.rounded_rectangle((x0, h * 0.4, x0 + w * 0.2, h * 0.418), 6 * s, fill=(170, 164, 190))
    for i, frac in enumerate((0.34, 0.3)):
        d.rounded_rectangle((x0, h * (0.445 + i * 0.035), x0 + w * frac, h * (0.46 + i * 0.035)), 6 * s,
                            fill=(120, 116, 140))
    # Play / Details pills
    py = h * 0.555
    d.rounded_rectangle((x0, py, x0 + w * 0.085, py + h * 0.075), h * 0.0375, fill=WHITE)
    tri = h * 0.03
    tx = x0 + w * 0.022
    d.polygon([(tx, py + h * 0.0375 - tri / 2), (tx, py + h * 0.0375 + tri / 2),
               (tx + tri * 0.9, py + h * 0.0375)], fill=BG)
    d.rounded_rectangle((tx + tri * 1.4, py + h * 0.03, x0 + w * 0.07, py + h * 0.045), 4 * s, fill=BG)
    ov = Image.new("RGBA", ui.size, (0, 0, 0, 0))
    ImageDraw.Draw(ov).rounded_rectangle((x0 + w * 0.095, py, x0 + w * 0.19, py + h * 0.075), h * 0.0375,
                                         fill=(255, 255, 255, 46))
    ui.alpha_composite(ov)
    d = ImageDraw.Draw(ui)
    # row title + posters
    d.rounded_rectangle((x0, h * 0.7, x0 + w * 0.16, h * 0.722), 6 * s, fill=WHITE)
    pw = int(w * 0.13)
    ph = int(pw * 1.42)
    for i in range(8):
        x = x0 + i * (pw + w * 0.018)
        pim = poster(pw, ph, rng, tint=(78, 60, 150) if i == 2 else None)
        paste_round(ui, pim, (x, h * 0.76), 12 * s, shadow_blur=0)
        if i == 0:  # focused tile: Apple TV lift + violet ring
            d.rounded_rectangle((x - 6 * s, h * 0.76 - 6 * s, x + pw + 6 * s, h * 0.76 + ph + 6 * s), 16 * s,
                                outline=VIOLET, width=int(6 * s))
    return ui.convert("RGB")


def render_appletv(w: int, h: int, tagline: str) -> Image.Image:
    s = h / 1646
    base = field(w, h, glow=(0.5, 0.35)).convert("RGBA")
    rng = random.Random(5)
    # TV: 16:9 screen with a thin bezel, centred in the safe area
    sw = int(w * 0.42)
    sh = int(sw * 9 / 16)
    cx, top = w / 2, h * 0.115
    bezel = int(18 * s)
    box = (cx - sw / 2 - bezel, top - bezel, cx + sw / 2 + bezel, top + sh + bezel)
    halo = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(halo).rounded_rectangle(box, 40 * s, fill=(120, 90, 255, 110))
    base.alpha_composite(halo.filter(ImageFilter.GaussianBlur(90 * s)))
    shadow(base, box, 40 * s, 50 * s, 200, (0, 30 * s))
    d = ImageDraw.Draw(base)
    d.rounded_rectangle(box, 40 * s, fill=(22, 20, 28), outline=(70, 66, 82), width=int(4 * s))
    screen = tv_ui(sw * 2, sh * 2, s * 2 * sw / 3840 * 3840 / 1650, rng).resize((sw, sh), Image.LANCZOS)
    paste_round(base, screen, (cx - sw / 2, top), 22 * s)
    # little stand
    d.rounded_rectangle((cx - 170 * s, box[3] + 4 * s, cx + 170 * s, box[3] + 22 * s), 8 * s, fill=(40, 38, 48))
    # remote, bottom right of the TV
    rx, ry = box[2] + 80 * s, box[3] - 430 * s
    rbox = (rx, ry, rx + 120 * s, ry + 420 * s)
    shadow(base, rbox, 60 * s, 30 * s, 170, (0, 16 * s))
    d.rounded_rectangle(rbox, 60 * s, fill=(196, 196, 204))
    d.rounded_rectangle((rx + 8 * s, ry + 8 * s, rx + 112 * s, ry + 150 * s), 52 * s, fill=(28, 28, 34))
    dot(base, rx + 60 * s, ry + 79 * s, 22 * s, (60, 60, 70))
    for i, yy in enumerate((200, 260)):
        dot(base, rx + 60 * s, ry + yy * s, 20 * s, (170, 170, 180))
    tri = 22 * s
    d.polygon([(rx + 52 * s, ry + 320 * s - tri / 2), (rx + 52 * s, ry + 320 * s + tri / 2),
               (rx + 52 * s + tri * 0.9, ry + 320 * s)], fill=(60, 60, 70))
    f = font("Montserrat.ttf", 104 * s, "SemiBold")
    centred_text(base, tagline, w / 2, box[3] + 95 * s, f, WHITE, w * 0.5)
    dot(base, w * 0.24, h * 0.22, 18 * s)
    dot(base, w * 0.79, h * 0.2, 11 * s, (200, 188, 255))
    return base.convert("RGB")


def film_strip(length: int, s: float, rng: random.Random) -> Image.Image:
    """Horizontal 35mm strip: black base, sprocket holes, toned abstract frames."""
    hgt = int(300 * s)
    strip = Image.new("RGBA", (length, hgt), (18, 16, 20, 255))
    d = ImageDraw.Draw(strip)
    hole_w, hole_h, pitch = 30 * s, 20 * s, 54 * s
    x = 14 * s
    while x < length:
        for yy in (16 * s, hgt - 16 * s - hole_h):
            d.rounded_rectangle((x, yy, x + hole_w, yy + hole_h), 5 * s, fill=(232, 222, 200, 255))
        x += pitch
    fw, fh = int(300 * s), int(hgt - 110 * s)
    x = 20 * s
    while x < length:
        top = rng.choice(SEPIA)
        fr = poster(fw, int(fw * 1.0), rng, tint=top).crop((0, 0, fw, fh))
        strip.paste(fr, (int(x), int(55 * s)))
        x += fw + 26 * s
    return strip


def place_strip(base, strip, cx, cy, angle, fade_side):
    lay = strip.rotate(angle, resample=Image.BICUBIC, expand=True)
    fade = Image.new("L", lay.size, 0)
    fd = ImageDraw.Draw(fade)
    for x in range(lay.width):
        t = x / lay.width if fade_side < 0 else 1 - x / lay.width
        fd.line([(x, 0), (x, lay.height)], fill=int(255 * min(1, 0.1 + t * 1.4) * 0.92))
    a = lay.getchannel("A")
    lay.putalpha(Image.composite(a, Image.new("L", a.size, 0), fade))
    base.alpha_composite(lay, (int(cx - lay.width / 2), int(cy - lay.height / 2)))


def deco_corner(d, x, y, sx, sy, s, col):
    L = 90 * s
    for k, inset in enumerate((0, 22 * s)):
        d.line([(x + sx * inset, y + sy * (inset + L - k * 30 * s)), (x + sx * inset, y + sy * inset),
                (x + sx * (inset + L - k * 30 * s), y + sy * inset)], fill=col, width=int(5 * s))
    d.ellipse([x + sx * 46 * s - 9 * s, y + sy * 46 * s - 9 * s, x + sx * 46 * s + 9 * s, y + sy * 46 * s + 9 * s],
              fill=col)


def render_silent(w: int, h: int, tagline: str) -> Image.Image:
    s = h / 1646
    base = field(w, h, glow=(0.5, 0.45), seed=9).convert("RGBA")
    rng = random.Random(21)
    place_strip(base, film_strip(int(w * 0.46), s, rng), w * 0.16, h * 0.33, 10, -1)
    place_strip(base, film_strip(int(w * 0.46), s, rng), w * 0.86, h * 0.55, 10, 1)
    # intertitle card
    cw, ch = w * 0.42, h * 0.58
    box = (w / 2 - cw / 2, h * 0.43 - ch / 2, w / 2 + cw / 2, h * 0.43 + ch / 2)
    halo = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(halo).rectangle(box, fill=(120, 90, 255, 90))
    base.alpha_composite(halo.filter(ImageFilter.GaussianBlur(110 * s)))
    shadow(base, box, 18 * s, 50 * s, 220, (0, 28 * s))
    card = Image.new("RGB", (int(cw), int(ch)), (16, 14, 14))
    noise = Image.effect_noise(card.size, 30).convert("RGB")
    card = Image.blend(card, noise, 0.06)
    paste_round(base, card, box[:2], 18 * s)
    d = ImageDraw.Draw(base)
    inset = 40 * s
    d.rectangle((box[0] + inset, box[1] + inset, box[2] - inset, box[3] - inset), outline=CREAM, width=int(5 * s))
    d.rectangle((box[0] + inset + 18 * s, box[1] + inset + 18 * s, box[2] - inset - 18 * s, box[3] - inset - 18 * s),
                outline=(170, 158, 134), width=int(2 * s))
    for (x, y, sx, sy) in ((box[0] + inset + 40 * s, box[1] + inset + 40 * s, 1, 1),
                           (box[2] - inset - 40 * s, box[1] + inset + 40 * s, -1, 1),
                           (box[0] + inset + 40 * s, box[3] - inset - 40 * s, 1, -1),
                           (box[2] - inset - 40 * s, box[3] - inset - 40 * s, -1, -1)):
        deco_corner(d, x, y, sx, sy, s, CREAM)
    cx = w / 2
    f1 = font("Cinzel.ttf", 150 * s, "Bold")
    f2 = font("PlayfairDisplay.ttf", 96 * s, "Regular")
    l1, l2 = "Silent Comedy", "Legends"
    f1 = centred_text(base, l1, cx, box[1] + ch * 0.27, f1, CREAM, cw * 0.72)
    # rule with a diamond
    yrule = box[1] + ch * 0.52
    d.line([(cx - cw * 0.22, yrule), (cx - 30 * s, yrule)], fill=(200, 186, 156), width=int(4 * s))
    d.line([(cx + 30 * s, yrule), (cx + cw * 0.22, yrule)], fill=(200, 186, 156), width=int(4 * s))
    d.polygon([(cx, yrule - 16 * s), (cx + 16 * s, yrule), (cx, yrule + 16 * s), (cx - 16 * s, yrule)], fill=VIOLET)
    centred_text(base, l2, cx, box[1] + ch * 0.575, f2, CREAM, cw * 0.6)
    f3 = font("Montserrat.ttf", 104 * s, "SemiBold")
    centred_text(base, tagline, cx, box[3] + 64 * s, f3, SOFT, w * 0.56)
    dot(base, w * 0.27, h * 0.15, 18 * s)
    dot(base, w * 0.74, h * 0.87, 12 * s, (200, 188, 255))
    return base.convert("RGB")


PAGES = {
    "default": (render_default, "Timeless films. Press play."),
    "cpp-appletv": (render_appletv, "Classic cinema for the big screen"),
    "cpp-silent-comedy": (render_silent, "Pratfalls, chases and daredevil stunts"),
}


def main() -> None:
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "marketing", "asc-creative")
    for name, (fn, tagline) in PAGES.items():
        canvases = CANVASES if name == "default" else {"header": CANVASES["header"]}
        for kind, (w, h) in canvases.items():
            img = fn(w, h, tagline)
            assert img.mode == "RGB" and img.size == (w, h)
            p = os.path.join(out, name, f"{kind}-{w}x{h}.png")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            img.save(p, optimize=True)
            print("wrote", p)


if __name__ == "__main__":
    main()
