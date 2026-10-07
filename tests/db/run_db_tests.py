#!/usr/bin/env python3
"""Run tests/db/test_*.sql against the live Supabase project (axgxpwgbpgcqjxoqwtnv).

Each file is one DO block that raises 'ALL_PASS' as its last statement, so everything it
wrote is rolled back; any other error is a failure. Needs the Supabase PAT in the Keychain
(service supabase-pat-clockin). Not part of run_fast.sh (network + live DB): run it after
every migration that touches the tables these files cover.
"""
import json
import pathlib
import subprocess
import sys
import urllib.error
import urllib.request

REF = "axgxpwgbpgcqjxoqwtnv"


def run(sql: str, pat: str) -> str:
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        data=json.dumps({"query": sql}).encode(),
        headers={"Authorization": f"Bearer {pat}", "Content-Type": "application/json",
                 "User-Agent": "curl/8.7.1"},  # Cloudflare 1010s urllib's default UA
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode()
    except urllib.error.HTTPError as e:
        return e.read().decode()


def main() -> int:
    pat = subprocess.run(["security", "find-generic-password", "-s", "supabase-pat-clockin", "-w"],
                         capture_output=True, text=True, check=True).stdout.strip()
    failed = 0
    for f in sorted(pathlib.Path(__file__).parent.glob("test_*.sql")):
        out = run(f.read_text(), pat)
        ok = "ALL_PASS" in out
        failed += not ok
        print(("PASS " if ok else "FAIL ") + f.name + ("" if ok else "\n  " + out[:600]))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
