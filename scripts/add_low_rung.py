"""Add a 240p (~0.35 Mbps) rung to every title's HLS ladder on the CDN.

The ladder bottomed out at 360p (~0.88 Mbps), so on a 512 kbps connection a film stalled
27 of every 40 seconds (LG self-check item 43 tests exactly that). This encodes a 240p
rendition from each stream's lowest existing rung (the sources were deleted after ingest),
uploads it as titles/<id>/v240/, and appends it to that master.m3u8. Players drop to it
on their own when the connection is slow; nothing in the apps changes.

Idempotent: a master that already lists v240/ is skipped.

Usage:  scripts/add_low_rung.py [--only <title id> ...] [--jobs 3]
Keys:   SPACES_KEY / SPACES_SECRET env, else Keychain haukley-spaces-key / haukley-spaces-secret.
"""
import argparse
import concurrent.futures
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CATALOG = ROOT / "web" / "watch" / "catalog" / "catalog.json"
CDN = "https://haukley-media.nyc3.cdn.digitaloceanspaces.com/"
ORIGIN = "https://haukley-media.nyc3.digitaloceanspaces.com/"  # masters read here: the CDN may cache them
BUCKET, REGION, SEG = "haukley-media", "nyc3", 6
RUNG = "v240"
VIDEO_KBPS, AUDIO_KBPS = 260, 64


def keychain(name):
    return subprocess.run(["security", "find-generic-password", "-s", name, "-w"],
                          check=True, capture_output=True, text=True).stdout.strip()


def s3():
    import boto3
    from botocore.config import Config
    return boto3.client("s3", region_name=REGION, endpoint_url=f"https://{REGION}.digitaloceanspaces.com",
                        aws_access_key_id=os.environ.get("SPACES_KEY") or keychain("haukley-spaces-key"),
                        aws_secret_access_key=os.environ.get("SPACES_SECRET") or keychain("haukley-spaces-secret"),
                        config=Config(retries={"max_attempts": 8, "mode": "standard"}))


def streams(only):
    cat = json.loads(CATALOG.read_text())
    out = []
    for t in cat["titles"]:
        items = [e["stream"] for e in t["episodes"]] if t["kind"] == "show" else [t["stream"]]
        for url in items:
            key = url[len(CDN):]  # titles/<id>[/eN]/master.m3u8
            if not only or t["id"] in only:
                out.append(key)
    return out


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"Cache-Control": "no-cache"}), timeout=60) as r:
        return r.read().decode()


def codecs_for(path, audio):
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                      "stream=profile,level", "-of", "json", str(path)],
                                     check=True, capture_output=True, text=True).stdout)["streams"][0]
    prof = {"High": "64", "Main": "4d", "Baseline": "42", "Constrained Baseline": "42"}[info["profile"]]
    avc = f"avc1.{prof}00{int(info['level']):02x}"
    return f"{avc},mp4a.40.2" if audio else avc


def process(key, client):
    base = key.rsplit("/", 1)[0]
    master = get(ORIGIN + key)
    if f"{RUNG}/index.m3u8" in master:
        return f"skip {base} (has {RUNG})"
    # The lowest existing rung is the encode source (smallest BANDWIDTH).
    entries = re.findall(r"#EXT-X-STREAM-INF:([^\n]+)\n([^\n#]+)", master)
    attrs, uri = min(entries, key=lambda e: int(re.search(r"BANDWIDTH=(\d+)", e[0]).group(1)))
    audio = "mp4a" in attrs
    with tempfile.TemporaryDirectory(prefix="haukley-rung-") as tmp:
        out = pathlib.Path(tmp) / RUNG
        out.mkdir()
        cmd = ["ffmpeg", "-v", "error", "-y", "-i", CDN + base + "/" + uri.strip(), "-map", "0:v:0"]
        if audio:
            cmd += ["-map", "0:a:0", "-c:a", "aac", "-b:a", f"{AUDIO_KBPS}k", "-ac", "2"]
        cmd += ["-vf", "scale=-2:240:flags=lanczos,setsar=1,format=yuv420p",
                "-c:v", "h264_videotoolbox", "-profile:v", "high", "-b:v", f"{VIDEO_KBPS}k",
                "-maxrate", f"{int(VIDEO_KBPS * 1.4)}k", "-bufsize", f"{VIDEO_KBPS * 2}k",
                "-force_key_frames", f"expr:gte(t,n_forced*{SEG})", "-sc_threshold", "0",
                "-f", "hls", "-hls_time", str(SEG), "-hls_playlist_type", "vod", "-hls_flags", "independent_segments",
                "-hls_segment_type", "mpegts", "-hls_segment_filename", str(out / "seg%04d.ts"), str(out / "index.m3u8")]
        subprocess.run(cmd, check=True)
        segs = sorted(out.glob("seg*.ts"))
        durs = [float(d) for d in re.findall(r"#EXTINF:([\d.]+)", (out / "index.m3u8").read_text())]
        rates = [s.stat().st_size * 8 / d for s, d in zip(segs, durs) if d > 0.5]
        peak, avg = int(max(rates)), int(sum(s.stat().st_size for s in segs) * 8 / sum(durs))
        dims = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                          "stream=width,height", "-of", "json", str(segs[0])],
                                         check=True, capture_output=True, text=True).stdout)["streams"][0]
        w, h = dims["width"], dims["height"]
        for f in sorted(out.iterdir()):
            playlist = f.suffix == ".m3u8"
            client.upload_file(str(f), BUCKET, f"{base}/{RUNG}/{f.name}", ExtraArgs={
                "ACL": "public-read",
                "ContentType": "application/vnd.apple.mpegurl" if playlist else "video/mp2t",
                "CacheControl": "public, max-age=300" if playlist else "public, max-age=31536000, immutable"})
        line = (f'#EXT-X-STREAM-INF:BANDWIDTH={peak},AVERAGE-BANDWIDTH={avg},RESOLUTION={w}x{h},'
                f'CODECS="{codecs_for(segs[0], audio)}"\n{RUNG}/index.m3u8\n')
        new_master = master.rstrip("\n") + "\n\n" + line
        client.put_object(Bucket=BUCKET, Key=key, Body=new_master.encode(), ACL="public-read",
                          ContentType="application/vnd.apple.mpegurl", CacheControl="public, max-age=300")
    return f"ok   {base}: {w}x{h}, {avg // 1000} kbps avg / {peak // 1000} peak, audio={audio}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--jobs", type=int, default=3)
    a = ap.parse_args()
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg not found")
    keys = streams(a.only)
    client = s3()
    print(f"{len(keys)} streams", flush=True)
    failed = []
    with concurrent.futures.ThreadPoolExecutor(a.jobs) as pool:
        futs = {pool.submit(process, k, client): k for k in keys}
        for f in concurrent.futures.as_completed(futs):
            try:
                print(f.result(), flush=True)
            except Exception as e:  # keep going; rerun picks up what's left
                failed.append(futs[f])
                print(f"FAIL {futs[f]}: {e}", flush=True)
    print(f"done, {len(failed)} failed {failed}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
