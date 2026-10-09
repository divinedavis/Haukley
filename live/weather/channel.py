#!/usr/bin/env python3
"""Haukley Weather: a 24/7 live channel made from NOAA / National Weather Service data.

Every RENDER_EVERY seconds it fetches public-domain NOAA products (NWS API forecasts and
alerts, the national radar loop, GOES satellite and CPC outlook images), draws a ~7.5-minute program of
1280x720 slides with Pillow and encodes it once with ffmpeg into 6-second HLS segments
(a "cycle"). A clock loop then plays the newest cycle on repeat as a live sliding-window
playlist, so the box encodes a few minutes of mostly-still video per render instead of
running a 24/7 encoder (the droplet has one vCPU shared with other sites).

Output (served by nginx at https://haukley.com/live/weather/):
  OUT/index.m3u8   master playlist (one variant)
  OUT/live.m3u8    live media playlist, rewritten every second
  OUT/c<id>/       one cycle's segments

Run: channel.py run --out DIR --state DIR      (the systemd service)
     channel.py render-once --out DIR --state DIR   (one cycle, for local checks)
The playlist logic (Timeline) needs only the standard library; Pillow and ffmpeg are
needed for rendering.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SEG = 6                      # seconds per HLS segment; every slide lasts a multiple of it
WINDOW = 5                   # segments listed in the live playlist
RENDER_EVERY = 15 * 60       # seconds between renders (NWS updates hourly at most)
KEEP_CYCLES = 3
FPS = 15
W, H = 1280, 720
BANDWIDTH = 900_000
UA = "Haukley Weather (hello@haukley.com)"   # api.weather.gov asks for a contact UA
ET = ZoneInfo("America/New_York")
HERE = Path(__file__).resolve().parent

CITIES = [
    ("New York", 40.7128, -74.0060), ("Los Angeles", 34.0522, -118.2437),
    ("Chicago", 41.8781, -87.6298), ("Houston", 29.7604, -95.3698),
    ("Phoenix", 33.4484, -112.0740), ("Philadelphia", 39.9526, -75.1652),
    ("Atlanta", 33.7490, -84.3880), ("Miami", 25.7617, -80.1918),
    ("Dallas", 32.7767, -96.7970), ("Denver", 39.7392, -104.9903),
    ("Seattle", 47.6062, -122.3321), ("San Francisco", 37.7749, -122.4194),
    ("Boston", 42.3601, -71.0589), ("Washington, D.C.", 38.9072, -77.0369),
    ("Minneapolis", 44.9778, -93.2650), ("New Orleans", 29.9511, -90.0715),
]
RADAR = "https://radar.weather.gov/ridge/standard/CONUS-LARGE_loop.gif"
# NCEP sites (WPC fronts map, NHC outlooks, SPC) answer 403 to the droplet's IP, so the maps
# come from NESDIS (GOES satellite) and CPC, which serve it.
MAPS = [  # (title, subtitle, url)
    ("Satellite", "GOES-East GeoColor · NOAA NESDIS",
     "https://cdn.star.nesdis.noaa.gov/GOES19/ABI/CONUS/GEOCOLOR/1250x750.jpg"),
    ("Tropical Atlantic", "GOES-East GeoColor · NOAA NESDIS",
     "https://cdn.star.nesdis.noaa.gov/GOES19/ABI/SECTOR/taw/GEOCOLOR/1800x1080.jpg"),
    ("6 to 10 Day Temperatures", "Outlook · NOAA Climate Prediction Center",
     "https://www.cpc.ncep.noaa.gov/products/predictions/610day/610temp.new.gif"),
]
ALERTS = "https://api.weather.gov/alerts/active?status=actual&message_type=alert&severity=Extreme,Severe"


# ---------------------------------------------------------------- live playlist (stdlib only)

class Timeline:
    """Plays cycles back to back as a live HLS window.

    A segment is listed once its end time has passed (as if it had just been recorded).
    Each cycle starts its timestamps at zero, so every cycle boundary carries
    EXT-X-DISCONTINUITY; EXT-X-DISCONTINUITY-SEQUENCE counts the tags that left the window.
    """

    def __init__(self, state: dict | None = None):
        s = state or {}
        self.seq = s.get("seq", 0)            # media sequence of entries[0]
        self.disc_seq = s.get("disc_seq", 0)
        self.entries = s.get("entries", [])   # [{cycle, idx, dur, disc}]
        self.cycle = s.get("cycle")           # cycle now playing
        self.idx = s.get("idx", 0)            # its next segment
        self.next_end = s.get("next_end")     # when that segment is "recorded"
        self._push_disc = False               # next appended segment starts a new cycle

    def state(self) -> dict:
        return dict(seq=self.seq, disc_seq=self.disc_seq, entries=self.entries,
                    cycle=self.cycle, idx=self.idx, next_end=self.next_end)

    def tick(self, now: float, cycles: dict[str, list[float]], newest: str) -> bool:
        """Advance to `now`. cycles maps id -> segment durations; returns True if changed."""
        if self.next_end is None or now - self.next_end > 60 or self.cycle not in cycles:
            # Cold start, a long outage, or the playing cycle was deleted: restart on the
            # newest cycle and backfill a full window so players can start at once.
            self.cycle, self.idx = newest, 0
            self.next_end = now - SEG * (WINDOW - 1)
            self._push_disc = True
        changed = False
        while now >= self.next_end:
            durs = cycles[self.cycle]
            if self.idx >= len(durs):
                self.cycle, self.idx, self._push_disc = newest, 0, True
                durs = cycles[self.cycle]
            disc = self._push_disc and bool(self.entries)
            self._push_disc = False
            self.entries.append(dict(cycle=self.cycle, idx=self.idx, dur=durs[self.idx], disc=disc))
            self.idx += 1
            self.next_end += durs[self.idx - 1]
            while len(self.entries) > WINDOW:
                gone = self.entries.pop(0)
                self.seq += 1
                if gone["disc"]:
                    self.disc_seq += 1
            changed = True
        return changed

    def referenced(self) -> set[str]:
        return {e["cycle"] for e in self.entries} | {self.cycle}

    def playlist(self) -> str:
        lines = ["#EXTM3U", "#EXT-X-VERSION:3", f"#EXT-X-TARGETDURATION:{SEG}",
                 f"#EXT-X-MEDIA-SEQUENCE:{self.seq}",
                 f"#EXT-X-DISCONTINUITY-SEQUENCE:{self.disc_seq}"]
        for e in self.entries:
            if e["disc"]:
                lines.append("#EXT-X-DISCONTINUITY")
            lines += [f"#EXTINF:{e['dur']:.3f},", f"c{e['cycle']}/seg{e['idx']:03d}.ts"]
        return "\n".join(lines) + "\n"


def master_playlist() -> str:
    return ("#EXTM3U\n#EXT-X-VERSION:3\n"
            f'#EXT-X-STREAM-INF:BANDWIDTH={BANDWIDTH},RESOLUTION={W}x{H},'
            f'FRAME-RATE={FPS}.000,CODECS="avc1.64001f,mp4a.40.2"\nlive.m3u8\n')


def write_atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


# ---------------------------------------------------------------- data

def fetch(url: str, timeout: int = 30) -> bytes:
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001 - NOAA hiccups are routine; retry then skip
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{url}: {last}")


def fetch_json(url: str) -> dict:
    return json.loads(fetch(url))


def city_points(state_dir: Path) -> dict:
    """lat/lon -> NWS forecast URLs, cached (the grid mapping rarely changes)."""
    cache_file = state_dir / "points.json"
    cache = json.loads(cache_file.read_text()) if cache_file.exists() else {}
    for name, lat, lon in CITIES:
        if name in cache:
            continue
        try:
            p = fetch_json(f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}")["properties"]
            cache[name] = dict(forecast=p["forecast"], hourly=p["forecastHourly"])
        except Exception as e:  # noqa: BLE001
            log(f"points {name}: {e}")
    write_atomic(cache_file, json.dumps(cache, indent=1))
    return cache


def summarize_city(forecast: dict, hourly: dict) -> dict:
    now = hourly["properties"]["periods"][0]
    periods = forecast["properties"]["periods"]
    return dict(
        temp=now["temperature"], unit=now.get("temperatureUnit", "F"),
        now=now.get("shortForecast", ""),
        wind=f"{now.get('windDirection', '')} {now.get('windSpeed', '')}".strip(),
        periods=[dict(name=p["name"], temp=p["temperature"], text=p.get("shortForecast", ""),
                      day=p.get("isDaytime", True)) for p in periods[:6]],
    )


def summarize_alerts(data: dict) -> dict:
    counts: dict[str, int] = {}
    for f in data.get("features", []):
        ev = f["properties"].get("event") or "Alert"
        counts[ev] = counts.get(ev, 0) + 1
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return dict(total=sum(counts.values()), top=top[:8])


def collect(state_dir: Path, work: Path) -> dict:
    data: dict = dict(cities=[], maps=[], radar=None, alerts=None)
    points = city_points(state_dir)
    for name, _, _ in CITIES:
        if name not in points:
            continue
        try:
            data["cities"].append(dict(name=name, **summarize_city(
                fetch_json(points[name]["forecast"]), fetch_json(points[name]["hourly"]))))
        except Exception as e:  # noqa: BLE001
            log(f"forecast {name}: {e}")
    try:
        data["alerts"] = summarize_alerts(fetch_json(ALERTS))
    except Exception as e:  # noqa: BLE001
        log(f"alerts: {e}")
    try:
        (work / "radar.gif").write_bytes(fetch(RADAR, timeout=60))
        data["radar"] = work / "radar.gif"
    except Exception as e:  # noqa: BLE001
        log(f"radar: {e}")
    for i, (title, sub, url) in enumerate(MAPS):
        try:
            p = work / f"map{i}{Path(url).suffix}"
            p.write_bytes(fetch(url))
            data["maps"].append((title, sub, p))
        except Exception as e:  # noqa: BLE001
            log(f"map {title}: {e}")
    return data


# ---------------------------------------------------------------- slides (Pillow)

BG_TOP, BG_BOT = (24, 14, 54), (8, 20, 48)
ACCENT, RED, WHITE, MUTED = (139, 108, 255), (230, 57, 70), (255, 255, 255), (178, 186, 214)
CARD = (255, 255, 255, 22)


def fonts():
    from PIL import ImageFont
    fdir = HERE / "fonts"
    def mont(size, weight=b"SemiBold"):
        f = ImageFont.truetype(str(fdir / "Montserrat.ttf"), size)
        try:
            f.set_variation_by_name(weight)
        except Exception:  # noqa: BLE001
            pass
        return f
    def osw(size):
        return ImageFont.truetype(str(fdir / "Oswald.ttf"), size)
    return mont, osw


class Painter:
    def __init__(self, updated: str):
        from PIL import Image, ImageDraw
        self.Image, self.ImageDraw = Image, ImageDraw
        self.mont, self.osw = fonts()
        self.updated = updated
        bg = Image.new("RGB", (W, H))
        d = ImageDraw.Draw(bg)
        for y in range(H):  # vertical gradient
            t = y / H
            d.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOT)))
        self.bg = bg

    def frame(self, title: str, subtitle: str = ""):
        im = self.bg.copy()
        d = self.ImageDraw.Draw(im, "RGBA")
        d.rectangle([0, 0, W, 64], fill=(0, 0, 0, 90))
        x = 32 + d.textlength("HAUKLEY ", font=self.osw(30))
        d.text((32, 32), "HAUKLEY", font=self.osw(30), fill=WHITE, anchor="lm")
        d.text((x, 32), "WEATHER", font=self.osw(30), fill=ACCENT, anchor="lm")
        x += d.textlength("WEATHER", font=self.osw(30)) + 18
        d.rounded_rectangle([x, 18, x + 66, 46], 6, fill=RED)
        d.text((x + 33, 32), "LIVE", font=self.mont(17, b"Bold"), fill=WHITE, anchor="mm")
        d.text((W - 32, 32), f"Updated {self.updated}", font=self.mont(20, b"Medium"),
               fill=MUTED, anchor="rm")
        d.text((48, 108), title, font=self.osw(52), fill=WHITE, anchor="lm")
        if subtitle:
            d.text((50, 152), subtitle, font=self.mont(22, b"Medium"), fill=MUTED, anchor="lm")
        d.rectangle([0, H - 44, W, H], fill=(0, 0, 0, 110))
        d.text((32, H - 22), "Data: NOAA / National Weather Service  ·  weather.gov",
               font=self.mont(18, b"Medium"), fill=MUTED, anchor="lm")
        d.text((W - 32, H - 22), "haukley.com", font=self.mont(18, b"SemiBold"),
               fill=ACCENT, anchor="rm")
        return im, d

    def fit(self, img, box):
        """Paste img scaled to fit box (x0, y0, x1, y1), centered."""
        x0, y0, x1, y1 = box
        img = img.convert("RGB")
        s = min((x1 - x0) / img.width, (y1 - y0) / img.height)
        img = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))))
        return img, (x0 + (x1 - x0 - img.width) // 2, y0 + (y1 - y0 - img.height) // 2)

    def wrap(self, d, text, font, width, max_lines):
        words, lines, cur = text.split(), [], ""
        for w in words:
            t = f"{cur} {w}".strip()
            if d.textlength(t, font=font) <= width:
                cur = t
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = lines[-1].rstrip(".,") + "…"
        return lines

    # --- slide types

    def intro(self, ncities: int):
        im, d = self.frame("")
        d.text((W // 2, 300), "HAUKLEY WEATHER", font=self.osw(96), fill=WHITE, anchor="mm")
        d.text((W // 2, 380), "Live national weather, around the clock", font=self.mont(30),
               fill=MUTED, anchor="mm")
        d.text((W // 2, 450), f"Radar  ·  Satellite  ·  Severe alerts  ·  {ncities} city forecasts",
               font=self.mont(24, b"Medium"), fill=ACCENT, anchor="mm")
        return im

    def alerts(self, a):
        im, d = self.frame("Severe Weather Alerts", "Active Extreme and Severe alerts in the U.S.")
        if not a["total"]:
            d.text((W // 2, 400), "No extreme or severe alerts right now", font=self.mont(40),
                   fill=WHITE, anchor="mm")
            return im
        d.text((48, 222), f"{a['total']} active", font=self.osw(44), fill=RED, anchor="lm")
        for i, (ev, n) in enumerate(a["top"]):
            col, row = i % 2, i // 2
            x, y = 48 + col * 600, 270 + row * 92
            d.rounded_rectangle([x, y, x + 572, y + 76], 12, fill=CARD)
            d.text((x + 24, y + 38), ev, font=self.mont(28), fill=WHITE, anchor="lm")
            d.text((x + 548, y + 38), str(n), font=self.osw(38), fill=ACCENT, anchor="rm")
        return im

    def city(self, c):
        im, d = self.frame(c["name"], "Local forecast · National Weather Service")
        d.rounded_rectangle([48, 190, 448, 640], 18, fill=CARD)
        d.text((248, 250), "NOW", font=self.mont(22, b"Bold"), fill=MUTED, anchor="mm")
        d.text((248, 360), f"{c['temp']}°", font=self.osw(150), fill=WHITE, anchor="mm")
        for j, line in enumerate(self.wrap(d, c["now"], self.mont(30), 350, 2)):
            d.text((248, 470 + j * 40), line, font=self.mont(30), fill=WHITE, anchor="mm")
        if c["wind"]:
            d.text((248, 590), f"Wind {c['wind']}", font=self.mont(22, b"Medium"),
                   fill=MUTED, anchor="mm")
        for i, p in enumerate(c["periods"]):
            col, row = i % 3, i // 3
            x, y = 476 + col * 256, 190 + row * 230
            d.rounded_rectangle([x, y, x + 240, y + 214], 16, fill=CARD)
            d.text((x + 120, y + 32), p["name"], font=self.mont(21, b"Bold"),
                   fill=ACCENT if p["day"] else MUTED, anchor="mm")
            d.text((x + 120, y + 92), f"{p['temp']}°", font=self.osw(60), fill=WHITE, anchor="mm")
            for j, line in enumerate(self.wrap(d, p["text"], self.mont(19, b"Medium"), 216, 3)):
                d.text((x + 120, y + 146 + j * 24), line, font=self.mont(19, b"Medium"),
                       fill=WHITE, anchor="mm")
        return im

    def map(self, title, sub, path):
        from PIL import Image
        im, d = self.frame(title, sub)
        img, pos = self.fit(Image.open(path), (48, 180, W - 48, H - 60))
        im.paste(img, pos)
        return im

    def radar_frames(self, path):
        from PIL import Image, ImageSequence
        gif = Image.open(path)
        base, _ = self.frame("National Radar", "Latest loop · NWS NEXRAD")
        out = []
        for fr in ImageSequence.Iterator(gif):
            im = base.copy()
            img, pos = self.fit(fr, (48, 176, W - 48, H - 52))
            im.paste(img, pos)
            out.append(im)
        return out


def build_program(data: dict, work: Path, updated: str) -> list[tuple[Path, float]]:
    """Draw every slide; returns ffmpeg concat entries (image, seconds). Each slide's total
    is a multiple of SEG so segment boundaries never split a cut."""
    p = Painter(updated)
    prog: list[tuple[Path, float]] = []
    n = 0

    def still(im, secs):
        nonlocal n
        path = work / f"s{n:03d}.png"
        n += 1
        im.save(path)
        prog.append((path, secs))

    def radar(secs):
        frames = p.radar_frames(data["radar"])
        paths = []
        for im in frames:
            still(im, 0)
            paths.append(prog.pop()[0])
        step, t, i = 0.4, 0.0, 0
        while t < secs - 1e-6:   # loop the frames, holding the newest one a little longer
            hold = 1.6 if i % len(paths) == len(paths) - 1 else step
            hold = min(hold, secs - t)
            prog.append((paths[i % len(paths)], round(hold, 3)))
            t += hold
            i += 1

    still(p.intro(len(data["cities"])), 2 * SEG)
    if data["radar"]:
        radar(6 * SEG)
    if data["alerts"] is not None:
        still(p.alerts(data["alerts"]), 3 * SEG)
    maps = list(data["maps"])
    if maps:
        still(p.map(*maps.pop(0)), 3 * SEG)
    for c in data["cities"]:
        still(p.city(c), 3 * SEG)
    for m in maps:
        still(p.map(*m), 3 * SEG)
    if data["radar"]:
        radar(6 * SEG)
    return prog


def encode(prog: list[tuple[Path, float]], work: Path, dest: Path) -> list[float]:
    """Encode the program into dest/seg%03d.ts; returns the segment durations."""
    lines = ["ffconcat version 1.0"]
    for path, secs in prog:
        lines += [f"file '{path.name}'", f"duration {secs:.3f}"]
    lines.append(f"file '{prog[-1][0].name}'")   # concat demuxer drops the last duration
    (work / "list.txt").write_text("\n".join(lines) + "\n")
    total = round(sum(s for _, s in prog), 3)
    dest.mkdir(parents=True, exist_ok=True)
    cmd = ["nice", "-n", "19", "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-f", "concat", "-safe", "0", "-i", str(work / "list.txt"),
           "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
           "-t", f"{total:.3f}", "-r", str(FPS), "-vf", "format=yuv420p",
           "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
           "-profile:v", "high", "-level", "3.1", "-b:v", "700k", "-maxrate", "800k",
           "-bufsize", "1600k", "-g", str(SEG * FPS), "-keyint_min", str(SEG * FPS),
           "-sc_threshold", "0", "-force_key_frames", f"expr:gte(t,n_forced*{SEG})",
           "-c:a", "aac", "-b:a", "64k", "-threads", "1",
           "-f", "hls", "-hls_time", str(SEG), "-hls_playlist_type", "vod",
           "-hls_segment_filename", str(dest / "seg%03d.ts"), str(dest / "cycle.m3u8")]
    subprocess.run(cmd, check=True, cwd=work, timeout=1800)
    durs = [float(l.split(":")[1].rstrip(",")) for l in (dest / "cycle.m3u8").read_text().splitlines()
            if l.startswith("#EXTINF:")]
    (dest / "durations.json").write_text(json.dumps(durs))
    return durs


def render(out: Path, state_dir: Path) -> str:
    cid = datetime.now(ET).strftime("%Y%m%d%H%M%S")
    work = state_dir / f"work-{cid}"
    work.mkdir(parents=True, exist_ok=True)
    try:
        t0 = time.time()
        data = collect(state_dir, work)
        if not data["cities"] and not data["radar"]:
            raise RuntimeError("no NOAA data fetched; keeping the previous cycle")
        updated = datetime.now(ET).strftime("%-I:%M %p ET, %a %b %-d")
        prog = build_program(data, work, updated)
        tmp = out / f".c{cid}"
        durs = encode(prog, work, tmp)
        os.replace(tmp, out / f"c{cid}")
        log(f"cycle {cid}: {len(durs)} segments, {sum(durs):.0f}s, "
            f"{len(data['cities'])} cities, rendered in {time.time() - t0:.0f}s")
        return cid
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ---------------------------------------------------------------- service

def log(msg: str) -> None:
    print(f"{datetime.now(ET):%Y-%m-%d %H:%M:%S} {msg}", flush=True)


def ready_cycles(out: Path) -> dict[str, list[float]]:
    found = {}
    for d in sorted(out.glob("c*")):
        f = d / "durations.json"
        if d.is_dir() and f.exists():
            found[d.name[1:]] = json.loads(f.read_text())
    return found


def prune(out: Path, keep: set[str]) -> None:
    cycles = sorted(ready_cycles(out))
    for cid in cycles[:-KEEP_CYCLES]:
        if cid not in keep:
            shutil.rmtree(out / f"c{cid}", ignore_errors=True)
    for d in out.glob(".c*"):   # half-written cycles from a crash
        if time.time() - d.stat().st_mtime > 3600:
            shutil.rmtree(d, ignore_errors=True)


def run(out: Path, state_dir: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    write_atomic(out / "index.m3u8", master_playlist())
    if not ready_cycles(out):
        render(out, state_dir)
    tl_file = state_dir / "timeline.json"
    tl = Timeline(json.loads(tl_file.read_text()) if tl_file.exists() else None)
    # A restart renders right away only if the newest cycle is already stale.
    last_render = (out / f"c{max(ready_cycles(out))}").stat().st_mtime
    busy = threading.Event()

    def bg_render():
        try:
            render(out, state_dir)
        except Exception as e:  # noqa: BLE001
            log(f"render failed: {e}")
        finally:
            busy.clear()

    while True:
        now = time.time()
        if now - last_render >= RENDER_EVERY and not busy.is_set():
            busy.set()
            last_render = now
            threading.Thread(target=bg_render, daemon=True).start()
        cycles = ready_cycles(out)
        if tl.tick(now, cycles, max(cycles)):
            write_atomic(out / "live.m3u8", tl.playlist())
            write_atomic(tl_file, json.dumps(tl.state()))
            prune(out, tl.referenced())
        time.sleep(1)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["run", "render-once"])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--state", type=Path, required=True)
    a = ap.parse_args()
    if a.cmd == "run":
        run(a.out, a.state)
    else:
        a.out.mkdir(parents=True, exist_ok=True)
        a.state.mkdir(parents=True, exist_ok=True)
        print(render(a.out, a.state))


if __name__ == "__main__":
    sys.exit(main())
