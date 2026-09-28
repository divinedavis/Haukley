"""Generate posters, cards and backdrops for every title in catalog.json.

Photos come from Picsum (Unsplash License, free to use) by id; titles are
typeset with open-license Google Fonts in scripts/fonts. Output goes to
src/assets/titles/<id>/ and src/catalog.generated.ts (bundled, no network).

Usage: .venv/bin/python scripts/make_posters.py
"""
import io
import urllib.request
import json
import pathlib

import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = pathlib.Path(__file__).resolve().parent.parent
FONTS = ROOT / "scripts" / "fonts"
OUT = ROOT / "src" / "assets" / "titles"
CACHE = ROOT / "scripts" / ".photo-cache"

POSTER = (600, 900)
CARD = (800, 450)
BACKDROP = (1920, 1080)


def font(name, size, weight="Bold"):
    f = ImageFont.truetype(str(FONTS / f"{name}.ttf"), size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


def body_font(size, weight="Medium"):
    return font("Montserrat", size, weight)


def photo(pid, size):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{pid}_{size[0]}x{size[1]}.jpg"
    if not path.exists():
        r = requests.get(f"https://picsum.photos/id/{pid}/{size[0]}/{size[1]}", timeout=60)
        r.raise_for_status()
        path.write_bytes(r.content)
    return Image.open(path).convert("RGB")


def photo_for(t, size):
    """A title's source image: its own still (real films, a frame from the film itself) when
    it has one, otherwise a Picsum photo by id."""
    if t.get("still"):
        img = Image.open(ROOT / t["still"]).convert("RGB")
        # Old transfers often carry black pillar/letterbox bars inside the frame: crop them off.
        mask = img.convert("L").point(lambda v: 255 if v > 24 else 0)
        box = mask.getbbox()
        if box and (box[2] - box[0]) * (box[3] - box[1]) > 0.4 * img.width * img.height:
            img = img.crop(box)
        return ImageOps.fit(img, size, Image.LANCZOS, centering=(0.5, 0.35))
    return photo(t["photo"], size)


def grade(img, tint, strength=0.28):
    """Cinematic grade: slight desaturation, contrast, and a color wash."""
    img = ImageEnhance.Color(img).enhance(0.75)
    img = ImageEnhance.Contrast(img).enhance(1.15)
    wash = Image.new("RGB", img.size, tuple(tint))
    return Image.blend(img, wash, strength)


def vertical_gradient(size, top_alpha, bottom_alpha, start=0.0):
    w, h = size
    grad = Image.new("L", (1, h))
    for y in range(h):
        t = max(0.0, (y / h - start) / (1 - start)) if start < 1 else 0
        grad.putpixel((0, y), int(top_alpha + (bottom_alpha - top_alpha) * t))
    return grad.resize(size)


def darken(img, mask):
    black = Image.new("RGB", img.size, "black")
    return Image.composite(black, img, mask)


def wrap_fit(draw, text, fname, max_w, max_size, max_lines=3, upper=True):
    """Largest font size where the title fits in max_lines within max_w."""
    text = text.upper() if upper else text
    words = text.split()
    for size in range(max_size, 20, -2):
        f = font(fname, size)
        lines, cur = [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            if draw.textlength(trial, font=f) <= max_w:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = w
        lines.append(cur)
        if len(lines) <= max_lines and all(draw.textlength(l, font=f) <= max_w for l in lines):
            return f, lines
    return font(fname, 20), [text]


def draw_lines(draw, lines, f, cx, y, fill="white", spacing=0.95, shadow=True):
    asc, desc = f.getmetrics()
    lh = int((asc + desc) * spacing)
    for line in lines:
        w = draw.textlength(line, font=f)
        x = cx - w / 2
        if shadow:
            draw.text((x + 3, y + 4), line, font=f, fill=(0, 0, 0, 160))
        draw.text((x, y), line, font=f, fill=fill)
        y += lh
    return y


def block_height(lines, f, spacing=0.95):
    asc, desc = f.getmetrics()
    return int((asc + desc) * spacing) * len(lines)


def uses_upper(t):
    return t["font"] not in ("Pacifico", "PlayfairDisplay", "AbrilFatface")


def make_poster(t, kind):
    w, h = POSTER
    img = grade(photo_for(t, (w * 2, h * 2)).resize(POSTER, Image.LANCZOS), t["tint"])
    layout = t["layout"]
    if layout == "top":
        img = darken(img, vertical_gradient(POSTER, 200, 0, 0).point(lambda v: v))
        img = darken(img, vertical_gradient(POSTER, 0, 170, 0.7))
    else:
        img = darken(img, vertical_gradient(POSTER, 60, 235, 0.35))
    d = ImageDraw.Draw(img, "RGBA")

    upper = uses_upper(t)
    f, lines = wrap_fit(d, t["title"], t["font"], w * 0.86, 150, 3, upper)
    th = block_height(lines, f)

    tag_f = body_font(17, "SemiBold")
    tag = t["tagline"].upper()
    tag_f2, tag_lines = wrap_fit_body(d, tag, w * 0.8, 17)

    if layout == "top":
        y = 60
        y = draw_lines(d, tag_lines, tag_f2, w / 2, y, fill=(235, 235, 235), spacing=1.3, shadow=False) + 18
        draw_lines(d, lines, f, w / 2, y)
    elif layout == "center":
        y = (h - th) / 2 + 40
        draw_lines(d, tag_lines, tag_f2, w / 2, 56, fill=(235, 235, 235), spacing=1.3, shadow=False)
        draw_lines(d, lines, f, w / 2, y)
    else:
        y = h - 150 - th
        draw_lines(d, tag_lines, tag_f2, w / 2, 56, fill=(235, 235, 235), spacing=1.3, shadow=False)
        draw_lines(d, lines, f, w / 2, y)

    # Billing block + release line, like a real one-sheet.
    cred_f = font("LeagueGothic", 22, "Regular")
    cred = t["credits"].upper()
    cw = d.textlength(cred, font=cred_f)
    if cw > w * 0.9:
        cred_f = font("LeagueGothic", int(22 * w * 0.9 / cw), "Regular")
        cw = d.textlength(cred, font=cred_f)
    d.text(((w - cw) / 2, h - 96), cred, font=cred_f, fill=(215, 215, 215))
    rel = f"{'STREAMING FREE' if kind == 'movie' else 'FREE SERIES'}  ·  ON HAUKLEY"
    rf = body_font(15, "Bold")
    rw = d.textlength(rel, font=rf)
    d.text(((w - rw) / 2, h - 58), rel, font=rf, fill=(255, 255, 255))
    return img


def wrap_fit_body(draw, text, max_w, size):
    f = body_font(size, "SemiBold")
    words, lines, cur = text.split(), [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if draw.textlength(trial, font=f) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    lines.append(cur)
    return f, lines[:2]


def make_card(t):
    w, h = CARD
    img = grade(photo_for(t, (w * 2, h * 2)).resize(CARD, Image.LANCZOS), t["tint"], 0.22)
    img = darken(img, vertical_gradient(CARD, 0, 210, 0.4))
    d = ImageDraw.Draw(img, "RGBA")
    f, lines = wrap_fit(d, t["title"], t["font"], w * 0.8, 96, 2, uses_upper(t))
    th = block_height(lines, f)
    draw_lines(d, lines, f, w / 2, h - 40 - th)
    return img


def horizontal_fade(size, left_alpha, span, power):
    """Black on the left fading to clear by `span` of the width."""
    w, h = size
    row = Image.new("L", (w, 1))
    for x in range(w):
        t = min(1.0, x / (w * span))
        row.putpixel((x, 0), int(left_alpha * (1 - t) ** power))
    return row.resize(size)


def make_backdrop(t):
    # Fades are baked in: gradient overlay PNGs don't render reliably on Fire OS.
    img = grade(photo_for(t, BACKDROP), t["tint"], 0.18)
    img = darken(img, horizontal_fade(BACKDROP, 235, 0.7, 1.5))
    bottom = vertical_gradient(BACKDROP, 0, 255, 0.45).point(lambda v: int(255 * (v / 255) ** 1.4))
    return darken(img, bottom)


EPISODE = (640, 360)


def make_episode_stills(t):
    """Each real episode's own frame (grabbed at ingest), cropped to 16:9 and lightly graded."""
    for e in t["episodes"]:
        src = Image.open(ROOT / e["still"]).convert("RGB")
        W, H = src.size
        h = min(H, int(W * 9 / 16))
        w = int(h * 16 / 9)
        frame = src.crop(((W - w) // 2, (H - h) // 2, (W - w) // 2 + w, (H - h) // 2 + h))
        yield e["number"], grade(frame.resize(EPISODE, Image.LANCZOS), t["tint"], 0.1)


ACCENT = (139, 108, 255)


def draw_wordmark(d, x, y, size, fill="white"):
    """'Haukley' plus the purple brand dot. Returns the drawn width."""
    f = font("Montserrat", size, "ExtraBold")
    d.text((x, y), "Haukley", font=f, fill=fill)
    w = d.textlength("Haukley", font=f)
    asc, _ = f.getmetrics()
    r = size * 0.11
    cx, cy = x + w + size * 0.16, y + asc - r * 1.1
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ACCENT)
    return w + size * 0.3


def wordmark_width(size):
    f = font("Montserrat", size, "ExtraBold")
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    return probe.textlength("Haukley", font=f) + size * 0.3


def brand_card(size, text_size):
    """Dark card with a purple glow and the centered wordmark (banners, icons, splash)."""
    w, h = size
    img = Image.new("RGB", size, (12, 12, 16))
    glow = Image.new("RGB", size, (0, 0, 0))
    ImageDraw.Draw(glow).ellipse([-w * 0.2, -h * 0.6, w * 0.8, h * 1.2], fill=(70, 40, 140))
    img = Image.blend(img, glow.filter(ImageFilter.GaussianBlur(max(1, w // 8))), 0.8)
    d = ImageDraw.Draw(img)
    tw = wordmark_width(text_size)
    draw_wordmark(d, (w - tw) / 2, h / 2 - text_size * 0.62, text_size)
    return img


# Launcher tiles sit in a row next to Netflix/YouTube, whose wordmarks span ~80% of the tile;
# ours at ~60% read as small on the TV, so size the wordmark to a fraction of the tile width.
TILE_WORDMARK = 0.82


def tv_tile(size):
    w, _ = size
    return brand_card(size, int(92 * TILE_WORDMARK * w / wordmark_width(92)))


def make_banner():
    """Android TV / Fire TV launcher banner (320x180 xhdpi), drawn at 2x and scaled down."""
    return tv_tile((640, 360)).resize((320, 180), Image.LANCZOS)


def make_firetv_icon():
    """Amazon Appstore 'Fire TV icon' (1280x720): the tile on the Fire TV home row."""
    return tv_tile((1280, 720))


def main():
    cat = json.loads((ROOT / "scripts" / "catalog.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    entries = []
    # Files are @2x so Android files them under drawable-xhdpi. Plain names land in
    # drawable-mdpi and get upscaled 2x on 320dpi Fire TVs (a 33 MB bitmap per backdrop).
    for kind, key in (("movie", "movies"), ("show", "shows")):
        for t in cat[key]:
            if t.get("still") and not (ROOT / t["still"]).exists():
                print("skip (no still yet)", t["id"])
                continue
            d = OUT / t["id"]
            d.mkdir(exist_ok=True)
            make_poster(t, kind).save(d / "poster@2x.jpg", quality=86, optimize=True, progressive=True)
            make_card(t).save(d / "card@2x.jpg", quality=84, optimize=True, progressive=True)
            make_backdrop(t).save(d / "backdrop@2x.jpg", quality=78, optimize=True, progressive=True)
            if kind == "show":
                for i, still in make_episode_stills(t):
                    still.save(d / f"ep{i}@2x.jpg", quality=82, optimize=True, progressive=True)
            entries.append((kind, t))
            print("ok", t["id"])

    make_banner().save(ROOT / "android/app/src/main/res/drawable/tv_banner.png")
    make_firetv_icon().save(ROOT / "marketing/firetv/firetv-icon-1280x720.png", optimize=True)

    # Only bundle films whose stream is already on the CDN (the rest are still ingesting).
    def live(url):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=15) as r:
                return r.status == 200
        except Exception:
            return False
    entries = [(k, t) for k, t in entries if not t.get("stream") or live(t["stream"])]
    print("bundled:", len(entries))

    fields = ("id", "title", "genre", "year", "rating", "tagline", "description", "credits", "license", "advisory")
    out = [
        "// Generated by scripts/make_posters.py from scripts/catalog.json. Do not edit.",
        "import type { Title } from './types';",
        "",
        "export const TITLES: Title[] = [",
    ]
    for kind, t in entries:
        props = [f"kind: '{kind}'"] + [f"{k}: {json.dumps(t[k])}" for k in fields if t.get(k) is not None]
        props.append(f"runtime: {json.dumps(t.get('runtime'))}" if kind == "movie" else f"seasons: {t['seasons']}")
        base = f"./assets/titles/{t['id']}"
        props += [
            f"poster: require('{base}/poster.jpg')",
            f"card: require('{base}/card.jpg')",
            f"backdrop: require('{base}/backdrop.jpg')",
        ]
        if kind == "show":
            stills = ", ".join(f"require('{base}/ep{e['number']}.jpg')" for e in t["episodes"])
            props.append(f"stills: [{stills}]")
            eps = [{k: e[k] for k in ("number", "name", "minutes", "summary", "stream")} for e in t["episodes"]]
            props.append(f"episodes: {json.dumps(eps, ensure_ascii=False)}")
        out.append("  { " + ", ".join(props) + " },")
    out.append("];")
    (ROOT / "src" / "catalog.generated.ts").write_text("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
