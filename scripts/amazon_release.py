#!/usr/bin/env python3
"""Ship a Fire TV build to the Amazon Appstore through the App Submission API, no console.

    python3 scripts/amazon_release.py ~/Downloads/Haukley-FireTV-1.4.apk --notes "..."           # dry run
    python3 scripts/amazon_release.py ~/Downloads/Haukley-FireTV-1.4.apk --notes "..." --commit  # submit

Opens (or reuses) the app's Edit, replaces the APK, sets the en-US "recent changes", then,
only with --commit, commits the Edit, which sends it to Amazon review and publishes it when
approved. A dry run leaves the Edit open in the Developer Console; re-running reuses it.

Credentials: Keychain amazon-appsubmission-client-id / -client-secret (security profile
"Haukley release", attached to the App Submission API under My Settings > API Access).
Docs: https://developer.amazon.com/docs/app-submission-api/overview.html
"""
import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

APP_ID = "amzn1.devportal.mobileapp.38d92c8636674264b2be58e97585b32d"
BASE = f"https://developer.amazon.com/api/appstore/v1/applications/{APP_ID}"
APK_TYPE = "application/vnd.android.package-archive"


def keychain(service):
    return subprocess.run(["security", "find-generic-password", "-a", "haukley", "-s", service, "-w"],
                          capture_output=True, text=True, check=True).stdout.strip()


def token():
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials", "scope": "appstore::apps:readwrite",
        "client_id": keychain("amazon-appsubmission-client-id"),
        "client_secret": keychain("amazon-appsubmission-client-secret"),
    }).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request("https://api.amazon.com/auth/o2/token", body)) as r:
            return json.load(r)["access_token"]
    except urllib.error.HTTPError as e:
        sys.exit(f"token -> {e.code}: {e.read().decode(errors='replace')[:300]}")


class Api:
    def __init__(self):
        self.auth = {"Authorization": f"Bearer {token()}"}

    def call(self, method, path, body=None, ctype="application/json", etag=None):
        headers = dict(self.auth)
        if etag:
            headers["If-Match"] = etag
        if body is not None:
            headers["Content-Type"] = ctype
            if ctype == "application/json":
                body = json.dumps(body).encode()
        req = urllib.request.Request(BASE + path, body, headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                raw = r.read()
                return (json.loads(raw) if raw.strip() else {}), r.headers.get("ETag")
        except urllib.error.HTTPError as e:
            sys.exit(f"{method} {path} -> {e.code}: {e.read().decode(errors='replace')[:600]}")


def apk_version(apk):
    sdk = Path.home() / "Library/Android/sdk/build-tools"
    aapt = sorted(sdk.glob("*/aapt"))[-1]
    line = subprocess.run([str(aapt), "dump", "badging", str(apk)], capture_output=True, text=True).stdout.splitlines()[0]
    return dict(kv.split("=", 1) for kv in line.replace("'", "").split()[1:4])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("apk", type=Path)
    ap.add_argument("--notes", required=True, help="en-US recent changes shown in the store")
    ap.add_argument("--commit", action="store_true", help="submit the Edit for review")
    a = ap.parse_args()
    v = apk_version(a.apk)
    if v.get("name") != "com.haukley.tv":
        sys.exit(f"{a.apk}: not com.haukley.tv ({v})")
    print(f"APK {v['name']} {v['versionName']} (code {v['versionCode']})")

    api = Api()
    edit, _ = api.call("GET", "/edits")
    if not edit.get("id"):
        edit, _ = api.call("POST", "/edits")
        print("opened edit", edit["id"])
    else:
        print("reusing open edit", edit["id"], edit.get("status", ""))
    e = f"/edits/{edit['id']}"

    apks, _ = api.call("GET", f"{e}/apks")
    if len(apks) != 1:
        sys.exit(f"expected exactly one APK in the edit, found {len(apks)}: {apks}")
    _, etag = api.call("GET", f"{e}/apks/{apks[0]['id']}")
    up, _ = api.call("PUT", f"{e}/apks/{apks[0]['id']}/replace", a.apk.read_bytes(), APK_TYPE, etag)
    print("replaced APK:", {k: up.get(k) for k in ("id", "versionCode", "name") if k in up} or up)

    listing, etag = api.call("GET", f"{e}/listings/en-US")
    listing["recentChanges"] = a.notes
    api.call("PUT", f"{e}/listings/en-US", listing, etag=etag)
    print("recent changes set")

    if not a.commit:
        print("dry run: edit left open; re-run with --commit to submit it for review")
        return
    _, etag = api.call("GET", e)
    api.call("POST", f"{e}/commit", etag=etag)
    print("committed: submitted to Amazon review")


if __name__ == "__main__":
    main()
