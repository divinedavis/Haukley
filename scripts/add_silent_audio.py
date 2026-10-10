#!/usr/bin/env python3
"""Give every video-only title on the CDN a silent stereo AAC track.

Roku's player never starts an HLS stream that has no audio: verified 2026-10-10 on a
Streaming Stick (OS 15.3.4) with a bare Video node — Metropolis and The General (silent
films, CODECS="avc1..." only) sat in "buffering" at position 0, His Girl Friday (avc1 +
mp4a) played. This remuxes each rung of a video-only title with silent audio WITHOUT
re-encoding the video (-c:v copy keeps the 6 s keyframe cuts, so segment boundaries and
names stay the same), rewrites master.m3u8 with mp4a.40.2 in CODECS, uploads over the old
keys and purges titles/<id>/* on the CDN (segments are cached for a year).

Idempotent: a master whose rungs already list mp4a is skipped.

Usage:  scripts/add_silent_audio.py [--only <title id> ...] [--jobs 3] [--dry-run]
Keys:   Keychain haukley-spaces-key / haukley-spaces-secret, digitalocean-token-haukley.
New titles get audio at ingest instead (ingest_free_titles.py encode, silent if none).
"""
import argparse
import concurrent.futures
import json
import pathlib
import re
import shutil
import subprocess
import tempfile
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CATALOG = ROOT / "web" / "watch" / "catalog" / "catalog.json"
CDN = "https://haukley-media.nyc3.cdn.digitaloceanspaces.com/"
ORIGIN = "https://haukley-media.nyc3.digitaloceanspaces.com/"  # read here: the CDN may cache the old files
BUCKET, REGION, SEG = "haukley-media", "nyc3", 6
AUDIO_KBPS = 64
# Silent track: stereo AAC-LC at 48 kHz. Same command shape the ingest uses for silent sources.
SILENT = ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
AUDIO_ARGS = ["-c:a", "aac", "-b:a", f"{AUDIO_KBPS}k", "-ac", "2", "-ar", "48000"]


def keychain(name):
    return subprocess.run(["security", "find-generic-password", "-s", name, "-w"],
                          check=True, capture_output=True, text=True).stdout.strip()


def s3():
    import boto3
    from botocore.config import Config
    return boto3.client("s3", region_name=REGION, endpoint_url=f"https://{REGION}.digitaloceanspaces.com",
                        aws_access_key_id=keychain("haukley-spaces-key"),
                        aws_secret_access_key=keychain("haukley-spaces-secret"),
                        config=Config(retries={"max_attempts": 8, "mode": "standard"}))


def get(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read().decode()


def streams():
    """(label, base key) for every film and episode in the published catalog."""
    out = []
    for t in json.loads(CATALOG.read_text())["titles"]:
        if t.get("kind") == "live":
            continue
        for label, url in ([(f"{t['id']} e{e['number']}", e["stream"]) for e in t["episodes"]]
                           if t.get("episodes") else [(t["id"], t["stream"])]):
            if url.startswith(CDN):
                out.append((label, url[len(CDN):].rsplit("/", 1)[0]))
    return out


def video_only(master):
    infs = [l for l in master.splitlines() if l.startswith("#EXT-X-STREAM-INF")]
    return bool(infs) and all("mp4a" not in l for l in infs)


def with_audio_master(master):
    """Same ladder, with mp4a.40.2 in CODECS and the audio bitrate added to BANDWIDTH."""
    def fix(line):
        if not line.startswith("#EXT-X-STREAM-INF"):
            return line
        line = re.sub(r'CODECS="([^"]*)"', lambda m: f'CODECS="{m.group(1)},mp4a.40.2"', line)
        for attr in ("BANDWIDTH", "AVERAGE-BANDWIDTH"):
            line = re.sub(rf"(?<![A-Z-]){attr}=(\d+)", lambda m: f"{attr}={int(m.group(1)) + AUDIO_KBPS * 1000}", line)
        return line
    return "\n".join(fix(l) for l in master.splitlines()) + "\n"


def probe_streams(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,start_time",
                          "-show_entries", "format=duration", "-of", "json", str(path)],
                         check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def av_offset(seg):
    """|audio start - video start| of one segment, seconds."""
    st = {s["codec_type"]: float(s.get("start_time") or 0) for s in probe_streams(seg)["streams"]}
    return abs(st.get("audio", 1e9) - st.get("video", 0))


def remux_rung(client, base, rung, tmp):
    """Download one rung, add silent audio, return the local output dir."""
    src, out = tmp / "src" / rung, tmp / "out" / rung
    src.mkdir(parents=True)
    out.mkdir(parents=True)
    playlist = get(f"{ORIGIN}{base}/{rung}/index.m3u8")
    segs = [l for l in playlist.splitlines() if l and not l.startswith("#")]
    for s in segs:
        client.download_file(BUCKET, f"{base}/{rung}/{s}", str(src / s))
    (src / "index.m3u8").write_text(playlist)
    # The silent track is cut to the playlist's length rather than with -shortest: -shortest
    # trimmed 1.7 s off The Phantom of the Opera's last segment.
    length = sum(float(x) for x in re.findall(r"#EXTINF:([\d.]+)", playlist))
    silent = SILENT[:-2] + ["-t", f"{length:.3f}"] + SILENT[-2:]
    cmd = ["ffmpeg", "-v", "error", "-y", "-allowed_extensions", "ALL", "-i", str(src / "index.m3u8"), *silent,
           "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", *AUDIO_ARGS,
           "-f", "hls", "-hls_time", str(SEG), "-hls_playlist_type", "vod", "-hls_flags", "independent_segments",
           "-hls_segment_type", "mpegts", "-hls_segment_filename", str(out / "seg%04d.ts"), str(out / "index.m3u8")]
    subprocess.run(cmd, check=True)
    new = sorted(p.name for p in out.glob("*.ts"))
    if new != sorted(segs):
        raise RuntimeError(f"{base}/{rung}: segment list changed ({len(segs)} -> {len(new)})")
    dur = lambda d: sum(float(x) for x in re.findall(r"#EXTINF:([\d.]+)", (d / "index.m3u8").read_text()))
    # Video is copied, not re-encoded, and the segment list must match exactly (above), so the
    # only drift is EXTINF re-measured from packet times: variable-frame-rate transfers move by
    # a frame per segment (The Phantom of the Opera: 1.7 s over 91 min). Allow 1 s or 0.05%.
    if abs(dur(out) - dur(src)) > max(1.0, 0.0005 * dur(src)):
        raise RuntimeError(f"{base}/{rung}: duration {dur(src):.1f}s -> {dur(out):.1f}s")
    worst = max(av_offset(out / s) for s in (new[0], new[len(new) // 2], new[-1]))
    if worst > 0.1:
        raise RuntimeError(f"{base}/{rung}: audio/video start offset {worst:.3f}s")
    return out, segs


def fix_title(label, base, dry_run=False):
    master = get(f"{ORIGIN}{base}/master.m3u8")
    if not video_only(master):
        return f"skip {label}: already has audio"
    rungs = [l.split("/")[0] for l in master.splitlines() if l and not l.startswith("#")]
    if dry_run:
        return f"would fix {label}: rungs {rungs}"
    client = s3()
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="haukley-audio-"))
    try:
        done = []
        for rung in rungs:
            out, segs = remux_rung(client, base, rung, tmp)
            done.append((rung, out, segs))
        # Upload only after every rung remuxed cleanly, playlists last.
        for rung, out, segs in done:
            for s in segs:
                client.upload_file(str(out / s), BUCKET, f"{base}/{rung}/{s}", ExtraArgs={
                    "ACL": "public-read", "ContentType": "video/mp2t",
                    "CacheControl": "public, max-age=31536000, immutable"})
        for rung, out, _ in done:
            client.upload_file(str(out / "index.m3u8"), BUCKET, f"{base}/{rung}/index.m3u8", ExtraArgs={
                "ACL": "public-read", "ContentType": "application/vnd.apple.mpegurl",
                "CacheControl": "public, max-age=300"})
        (tmp / "master.m3u8").write_text(with_audio_master(master))
        client.upload_file(str(tmp / "master.m3u8"), BUCKET, f"{base}/master.m3u8", ExtraArgs={
            "ACL": "public-read", "ContentType": "application/vnd.apple.mpegurl", "CacheControl": "public, max-age=300"})
        purge(base)
        return f"ok   {label}: {len(done)} rungs, {sum(len(s) for _, _, s in done)} segments"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def purge(base):
    token = keychain("digitalocean-token-haukley")
    req = urllib.request.Request("https://api.digitalocean.com/v2/cdn/endpoints",
                                 headers={"Authorization": f"Bearer {token}"})
    eps = json.loads(urllib.request.urlopen(req, timeout=30).read())["endpoints"]
    ep = next(e for e in eps if e["origin"].startswith(BUCKET + "."))
    body = json.dumps({"files": [f"{base}/*"]}).encode()
    req = urllib.request.Request(f"https://api.digitalocean.com/v2/cdn/endpoints/{ep['id']}/cache", data=body,
                                 method="DELETE", headers={"Authorization": f"Bearer {token}",
                                                           "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=30).read()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", nargs="*", default=[])
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    todo = [(l, b) for l, b in streams() if not a.only or l in a.only or b.split("/")[1] in a.only]
    with concurrent.futures.ThreadPoolExecutor(a.jobs) as ex:
        futs = {ex.submit(fix_title, l, b, a.dry_run): l for l, b in todo}
        for f in concurrent.futures.as_completed(futs):
            try:
                print(f.result(), flush=True)
            except Exception as e:  # noqa: BLE001 - report every title, keep going
                print(f"FAIL {futs[f]}: {e}", flush=True)


if __name__ == "__main__":
    main()
