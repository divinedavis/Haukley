"""Ingest the public-domain / CC-BY films in scripts/free_titles.json into HLS for the CDN.

One film at a time (the Mac has little free disk): download the source, cut modern
logos/cards (source.trim_start / source.trim_end, seconds), encode an HLS ladder with
aligned 6 s segments, grab a still for key art, then delete the source.

Stages:
  download  fetch sources into WORK/src/
  sheets    contact sheets of the first/last 60 s (to pick exact trims), WORK/sheets/
  encode    HLS ladder into WORK/hls/<id>/ (+ scripts/stills/<id>.jpg), deletes the source
  upload    push WORK/hls/<id>/ to the Spaces bucket (needs SPACES_KEY/SPACES_SECRET env)

Usage: .venv/bin/python scripts/ingest_free_titles.py encode [--only id,id] [--keep-source]
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


def titles(only):
    data = json.loads((ROOT / "scripts" / "free_titles.json").read_text())
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
    run(["curl", "-fL", "--retry", "5", "--retry-delay", "5", "-C", "-", "-A", UA, "-o", str(tmp), t["source"]["url"]])
    tmp.rename(dst)
    return dst


def sheets(t):
    src = download(t)
    dur = float(probe(src)["format"]["duration"])
    out = WORK / "sheets"
    out.mkdir(parents=True, exist_ok=True)
    for name, start in (("head", 0), ("tail", max(0, dur - 60))):
        # One frame every 2 s over 60 s, 6x5 grid, timestamps burned in.
        vf = (f"fps=0.5,scale=320:-2,drawtext=text='%{{pts\\:hms}}':x=6:y=6:fontsize=18:fontcolor=yellow:box=1:boxcolor=black@0.6,"
              "tile=6x5")
        run(["ffmpeg", "-v", "error", "-y", "-ss", str(start), "-t", "60", "-i", str(src), "-vf", vf,
             "-frames:v", "1", str(out / f"{t['id']}-{name}.jpg")])
    print(f"  duration {dur:.1f}s; tail sheet starts at {max(0, dur - 60):.1f}s")


def has_real_audio(t, info):
    if t["source"].get("mute"):
        return False
    audio = [s for s in info["streams"] if s["codec_type"] == "audio"]
    return bool(audio) and not t["source"].get("silent_audio")


def encode(t, keep_source=False):
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

    n = len(rungs)
    split = f"[0:v]split={n}" + "".join(f"[s{i}]" for i in range(n)) + ";"
    # Square pixels, even dimensions, capped to each rung's height.
    scales = ";".join(f"[s{i}]scale=-2:'min({h},ih)':flags=lanczos,setsar=1,format=yuv420p[v{i}]" for i, (h, _) in enumerate(rungs))
    cmd = ["ffmpeg", "-v", "error", "-stats", "-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(src),
           "-filter_complex", split + scales]
    for i, (h, kbps) in enumerate(rungs):
        cmd += ["-map", f"[v{i}]", f"-c:v:{i}", "h264_videotoolbox", f"-b:v:{i}", f"{kbps}k",
                f"-maxrate:v:{i}", f"{int(kbps * 1.4)}k", f"-bufsize:v:{i}", f"{kbps * 2}k", f"-profile:v:{i}", "high"]
        if audio:
            cmd += ["-map", "0:a:0", f"-c:a:{i}", "aac", f"-b:a:{i}", "128k", f"-ac:a:{i}", "2"]
    cmd += ["-force_key_frames", f"expr:gte(t,n_forced*{SEG})", "-sc_threshold", "0"]
    vsm = " ".join(f"v:{i},a:{i}" if audio else f"v:{i}" for i in range(n))
    cmd += ["-f", "hls", "-hls_time", str(SEG), "-hls_playlist_type", "vod", "-hls_flags", "independent_segments",
            "-hls_segment_type", "mpegts", "-hls_segment_filename", str(out / "v%v" / "seg%04d.ts"),
            "-master_pl_name", "master.m3u8", "-var_stream_map", vsm, str(out / "v%v" / "index.m3u8")]
    print(f"encode {t['id']}: {src_h}p source, rungs {[h for h, _ in rungs]}, audio={audio}, {start:.1f}-{end:.1f}s", flush=True)
    run(cmd)

    # Still for key art: a frame about a third of the way in (past the titles).
    STILLS.mkdir(exist_ok=True)
    at = start + (end - start) * float(t["source"].get("still_at", 0.33))
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at:.1f}", "-i", str(src), "-frames:v", "1",
         "-vf", "scale=1920:-2:flags=lanczos,setsar=1", "-q:v", "3", str(STILLS / f"{t['id']}.jpg")])
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
    print(f"upload {t['id']}: {len(files)} files")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["download", "sheets", "encode", "upload"])
    ap.add_argument("--only", default="")
    ap.add_argument("--keep-source", action="store_true")
    a = ap.parse_args()
    only = {x for x in a.only.split(",") if x}
    for t in titles(only):
        if a.stage == "download":
            download(t)
        elif a.stage == "sheets":
            sheets(t)
        elif a.stage == "encode":
            encode(t, a.keep_source)
        else:
            upload(t)
