"""Ingest the public-domain / CC-BY films in scripts/free_titles.json into HLS for the CDN.

One film at a time (the Mac has little free disk): download the source, cut modern
logos/cards (source.trim_start / source.trim_end, seconds), encode an HLS ladder with
aligned 6 s segments, grab a still for key art, then delete the source.

Stages:
  download  fetch sources into WORK/src/
  sheets    contact sheets of the first/last 60 s (to pick exact trims), WORK/sheets/
  encode    HLS ladder into WORK/hls/<id>/ (+ scripts/stills/<id>.jpg), deletes the source
  upload    push WORK/hls/<id>/ to the Spaces bucket (needs SPACES_KEY/SPACES_SECRET env)
  all       encode -> upload -> delete the local HLS, title by title (keeps disk use low)

Usage: .venv/bin/python scripts/ingest_free_titles.py encode [--only id,id] [--keep-source]

Re-ingesting a title (e.g. a new trim) rewrites the same segment keys, and the CDN caches
segments for a year: purge titles/<id>/* on the Spaces CDN endpoint afterwards (DELETE
/v2/cdn/endpoints/<id>/cache with the digitalocean-token-haukley Keychain token), or
viewers keep getting the old cut. Check the fix against the CDN URL, not the origin.

Series: --series reads scripts/free_titles_series.json instead, and --only names shows. Each
episode is ingested as "<show>/e<N>", so it lands at titles/<show>/e<N>/master.m3u8 on the CDN
and its still at scripts/stills/<show>/e<N>.jpg. Per-episode trims live in the episode's
source, exactly like a film's.
"""
import argparse
import json
import mimetypes
import os
import pathlib
import shutil
import subprocess
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORK = pathlib.Path.home() / "Movies" / "haukley-ingest"
STILLS = ROOT / "scripts" / "stills"
SEG = 6
# Height -> video bitrate (kbps). Only rungs at or below the source height, plus 360p always.
LADDER = [(1080, 5000), (720, 2800), (480, 1400), (360, 800)]
BUCKET = "haukley-media"
REGION = "nyc3"
UA = "Mozilla/5.0 (Macintosh) HaukleyIngest/1.0"


def titles(only, series=False, listfile="free_titles.json"):
    if series:
        shows = json.loads((ROOT / "scripts" / "free_titles_series.json").read_text())
        if not only:
            sys.exit("--series needs --only <show ids>: only low-risk shows are cleared for ingest")
        return [{"id": f"{s['id']}/e{e['number']}", "source": e["source"]}
                for s in shows if s["id"] in only and s.get("kind") == "show"
                for e in s["episodes"] if not e.get("skip")]
    data = json.loads((ROOT / "scripts" / listfile).read_text())
    data = [t for t in data if not t.get("skip")]
    return [t for t in data if not only or t["id"] in only]


def src_path(t):
    ext = pathlib.Path(urllib.parse.urlparse(t["source"]["url"]).path).suffix or ".mp4"
    return WORK / "src" / f"{t['id']}{ext}"


def run(cmd, **kw):
    print("  $", " ".join(str(c) for c in cmd)[:220], flush=True)
    return subprocess.run(cmd, check=True, **kw)


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
                         check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def download(t):
    dst = src_path(t)
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".part")
    print(f"download {t['id']} ({t['source']['bytes'] / 1e6:.0f} MB)", flush=True)
    # archive.org drops long transfers now and then; resume the .part file on any error.
    for attempt in range(8):
        try:
            run(["curl", "-fL", "--retry", "5", "--retry-delay", "5", "--retry-all-errors", "-C", "-", "-A", UA,
                 "-o", str(tmp), t["source"]["url"]])
            break
        except subprocess.CalledProcessError as e:
            if attempt == 7:
                raise
            print(f"  download interrupted (curl {e.returncode}); resuming", flush=True)
    tmp.rename(dst)
    return dst


def sheets(t):
    from PIL import Image, ImageDraw

    src = download(t)
    dur = float(probe(src)["format"]["duration"])
    out = WORK / "sheets"
    tmp = WORK / "frames"
    (out / t["id"]).parent.mkdir(parents=True, exist_ok=True)
    for name, start in (("head", 0), ("tail", max(0, dur - 60))):
        # One frame per second over 60 s, 10x6 grid, each labeled with its source timestamp.
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir()
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-t", "60", "-i", str(src),
             "-vf", "fps=1,scale=240:-2", str(tmp / "f%03d.jpg")])
        frames = sorted(tmp.glob("*.jpg"))
        w, h = Image.open(frames[0]).size
        sheet = Image.new("RGB", (w * 10, (h + 18) * 6), "black")
        d = ImageDraw.Draw(sheet)
        for i, f in enumerate(frames[:60]):
            x, y = (i % 10) * w, (i // 10) * (h + 18)
            sheet.paste(Image.open(f), (x, y + 18))
            d.text((x + 4, y + 3), f"{start + i:.0f}s", fill="yellow")
        sheet.save(out / f"{t['id']}-{name}.jpg", quality=80)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"  duration {dur:.1f}s; tail sheet starts at {max(0, dur - 60):.1f}s")


def has_real_audio(t, info):
    if t["source"].get("mute"):
        return False
    audio = [s for s in info["streams"] if s["codec_type"] == "audio"]
    return bool(audio) and not t["source"].get("silent_audio")


def display_aspect(t, v):
    """The width/height the picture should be shown at. A source's "display_aspect" ("4:3")
    overrides it for files whose pixels are already distorted with no SAR to say so (e.g. a
    4:3 film uploaded at 540x360); otherwise it is the probed size times the SAR, so DVD/NARA
    transfers (720x480 at 8:9, 720x576 at 16:15) come out 4:3 rather than 3:2 or 5:4."""
    override = t["source"].get("display_aspect")
    if override:
        a, b = override.split(":")
        return int(a) / int(b)
    sar = v.get("sample_aspect_ratio") or "1:1"
    n, d = (int(x) for x in sar.split(":")) if ":" in sar else (1, 1)
    if n <= 0 or d <= 0:
        n, d = 1, 1
    return int(v["width"]) * n / d / int(v["height"])


def square_pixels(dar):
    """ffmpeg filter: resample to square pixels at the display aspect, keeping the height."""
    # setparams first: some NARA MPEG-2 transfers carry a log100 transfer tag that the scaler
    # refuses and that would otherwise ride into every rung.
    return ("setparams=color_trc=bt709:colorspace=bt709:color_primaries=bt709,"
            f"scale='trunc(ih*{dar:.6f}/2)*2':ih:flags=lanczos,setsar=1")


def check_aspect(out, dar, label):
    """Fail the ingest if the top rung isn't shown at the display aspect (2% slack for even
    rounding). This is the check that would have caught 720x480 8:9 sources playing at 3:2."""
    seg = next((out / "v0").glob("*.ts"))
    w, h = (int(x) for x in subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
         "-of", "csv=p=0", str(seg)], check=True, capture_output=True, text=True).stdout.split()[0].split(",")[:2])
    if abs(w / h - dar) / dar > 0.02:
        sys.exit(f"{label}: encoded {w}x{h} ({w / h:.3f}) but the display aspect is {dar:.3f}")


# Silent stereo AAC for sources with no usable audio (silent films, muted tracks). Every rung
# must carry an audio track: Roku's player never starts an HLS stream without one (verified
# 2026-10-10 on a Streaming Stick: video-only titles sat in "buffering" at position 0).
SILENT_INPUT = ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]


def ladder_cmd(src, out, rungs, start, end, dar, real_audio):
    """The ffmpeg command for one title's HLS ladder. Pure, so tests can check its shape."""
    n = len(rungs)
    # Square pixels at the display aspect before the ladder (see display_aspect), or every rung
    # plays stretched or squeezed.
    split = f"[0:v]{square_pixels(dar)},split={n}" + "".join(f"[s{i}]" for i in range(n)) + ";"
    # Square pixels, even dimensions, capped to each rung's height.
    scales = ";".join(f"[s{i}]scale=-2:'min({h},ih)':flags=lanczos,setsar=1,format=yuv420p[v{i}]" for i, (h, _) in enumerate(rungs))
    cmd = ["ffmpeg", "-v", "error", "-stats", "-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(src)]
    if not real_audio:
        cmd += SILENT_INPUT
    cmd += ["-filter_complex", split + scales]
    for i, (h, kbps) in enumerate(rungs):
        cmd += ["-map", f"[v{i}]", f"-c:v:{i}", "h264_videotoolbox", f"-b:v:{i}", f"{kbps}k",
                f"-maxrate:v:{i}", f"{int(kbps * 1.4)}k", f"-bufsize:v:{i}", f"{kbps * 2}k", f"-profile:v:{i}", "high"]
        if real_audio:
            cmd += ["-map", "0:a:0", f"-c:a:{i}", "aac", f"-b:a:{i}", "128k", f"-ac:a:{i}", "2"]
        else:
            cmd += ["-map", "1:a:0", f"-c:a:{i}", "aac", f"-b:a:{i}", "64k", f"-ac:a:{i}", "2", f"-ar:a:{i}", "48000"]
    if not real_audio:
        cmd += ["-shortest"]  # the silent source never ends
    cmd += ["-force_key_frames", f"expr:gte(t,n_forced*{SEG})", "-sc_threshold", "0"]
    vsm = " ".join(f"v:{i},a:{i}" for i in range(n))
    cmd += ["-f", "hls", "-hls_time", str(SEG), "-hls_playlist_type", "vod", "-hls_flags", "independent_segments",
            "-hls_segment_type", "mpegts", "-hls_segment_filename", str(out / "v%v" / "seg%04d.ts"),
            "-master_pl_name", "master.m3u8", "-var_stream_map", vsm, str(out / "v%v" / "index.m3u8")]
    return cmd


def check_audio(out, label):
    """Fail the ingest if a rung came out without an audio stream (Roku won't play it)."""
    for rung in sorted(p for p in out.iterdir() if p.is_dir()):
        seg = next(rung.glob("*.ts"))
        kinds = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0",
                                str(seg)], check=True, capture_output=True, text=True).stdout.split()
        if "audio" not in kinds:
            sys.exit(f"{label}: {rung.name} has no audio track")


def encode(t, keep_source=False):
    if (WORK / "hls" / t["id"] / "master.m3u8").exists():
        print(f"encode {t['id']}: already done")
        return
    free = shutil.disk_usage(WORK).free / 1e9
    if free < 6:
        sys.exit(f"stopping before {t['id']}: only {free:.1f} GB free (upload + clear WORK/hls first)")
    src = download(t)
    info = probe(src)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    src_h = int(v["height"])
    dur = float(info["format"]["duration"])
    start = float(t["source"].get("trim_start", 0))
    end = dur - float(t["source"].get("trim_end", 0))
    rungs = [(h, b) for h, b in LADDER if h <= max(src_h, 360) + 8]
    if not rungs:
        rungs = [LADDER[-1]]
    audio = has_real_audio(t, info)
    out = WORK / "hls" / t["id"]
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)

    dar = display_aspect(t, v)
    cmd = ladder_cmd(src, out, rungs, start, end, dar, audio)
    print(f"encode {t['id']}: {src_h}p source, rungs {[h for h, _ in rungs]}, audio={audio}, {start:.1f}-{end:.1f}s", flush=True)
    run(cmd)
    check_aspect(out, dar, t["id"])
    check_audio(out, t["id"])

    # Still for key art: a frame about a third of the way in (past the titles).
    (STILLS / f"{t['id']}.jpg").parent.mkdir(parents=True, exist_ok=True)
    at = start + (end - start) * float(t["source"].get("still_at", 0.33))
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at:.1f}", "-i", str(src), "-frames:v", "1",
         "-vf", f"{square_pixels(dar)},scale=1920:-2:flags=lanczos,setsar=1", "-q:v", "3", str(STILLS / f"{t['id']}.jpg")])
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"  -> {out} ({size / 1e6:.0f} MB)")
    if not keep_source:
        src.unlink()


def upload(t):
    import boto3
    from botocore.config import Config

    out = WORK / "hls" / t["id"]
    if not (out / "master.m3u8").exists():
        sys.exit(f"{t['id']}: not encoded yet")
    s3 = boto3.client("s3", region_name=REGION, endpoint_url=f"https://{REGION}.digitaloceanspaces.com",
                      aws_access_key_id=os.environ["SPACES_KEY"], aws_secret_access_key=os.environ["SPACES_SECRET"],
                      config=Config(retries={"max_attempts": 8, "mode": "standard"}))
    files = sorted(p for p in out.rglob("*") if p.is_file())
    for p in files:
        key = f"titles/{t['id']}/{p.relative_to(out).as_posix()}"
        playlist = p.suffix == ".m3u8"
        s3.upload_file(str(p), BUCKET, key, ExtraArgs={
            "ACL": "public-read",
            "ContentType": "application/vnd.apple.mpegurl" if playlist else (mimetypes.guess_type(p.name)[0] or "video/mp2t"),
            "CacheControl": "public, max-age=300" if playlist else "public, max-age=31536000, immutable",
        })
    print(f"upload {t['id']}: {len(files)} files", flush=True)
    marker = WORK / "uploaded" / t["id"]
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["download", "sheets", "encode", "upload", "all"])
    ap.add_argument("--only", default="")
    ap.add_argument("--keep-source", action="store_true")
    ap.add_argument("--series", action="store_true", help="ingest episodes from free_titles_series.json")
    ap.add_argument("--list", default="free_titles.json", help="films list in scripts/ (e.g. free_titles_black.json)")
    a = ap.parse_args()
    only = {x for x in a.only.split(",") if x}
    for t in titles(only, a.series, a.list):
        if a.stage == "download":
            download(t)
        elif a.stage == "sheets":
            sheets(t)
        elif a.stage == "encode":
            encode(t, a.keep_source)
        elif a.stage == "all":
            if (WORK / "uploaded" / t["id"]).exists():
                print(f"{t['id']}: already uploaded")
                continue
            # Head/tail contact sheets first (the source is downloaded anyway), so every
            # title's opening and closing can be reviewed for modern cards after the run.
            if not (WORK / "sheets" / f"{t['id']}-head.jpg").exists():
                sheets(t)
            encode(t, a.keep_source)
            upload(t)
            shutil.rmtree(WORK / "hls" / t["id"])
        else:
            upload(t)
