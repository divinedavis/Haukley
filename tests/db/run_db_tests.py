#!/usr/bin/env python3
"""Run tests/db/test_*.sql against the live Supabase project (axgxpwgbpgcqjxoqwtnv), then
check the project's auth settings (audit 2026-10-07 M2/L5).

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


def auth_config_problems(cfg: dict) -> list:
    """Auth settings the app relies on. Never print the config: it holds secrets."""
    bad = []
    if cfg.get("security_manual_linking_enabled"):
        bad.append("manual identity linking is on (0015 guard assumes off)")
    if not cfg.get("security_update_password_require_reauthentication"):
        bad.append("password update does not require a fresh session")
    for u in (cfg.get("uri_allow_list") or "").split(","):
        if u and not u.startswith("https://haukley.com/"):
            bad.append(f"redirect allow-list has a non-haukley.com entry: {u}")
    if cfg.get("external_anonymous_users_enabled"):
        bad.append("anonymous sign-ins are on")
    return bad


def main() -> int:
    pat = subprocess.run(["security", "find-generic-password", "-s", "supabase-pat-clockin", "-w"],
                         capture_output=True, text=True, check=True).stdout.strip()
    failed = 0
    for f in sorted(pathlib.Path(__file__).parent.glob("test_*.sql")):
        out = run(f.read_text(), pat)
        ok = "ALL_PASS" in out
        failed += not ok
        print(("PASS " if ok else "FAIL ") + f.name + ("" if ok else "\n  " + out[:600]))
    req = urllib.request.Request(f"https://api.supabase.com/v1/projects/{REF}/config/auth",
                                 headers={"Authorization": f"Bearer {pat}", "User-Agent": "curl/8.7.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        problems = auth_config_problems(json.loads(r.read()))
    failed += bool(problems)
    print(("PASS " if not problems else "FAIL ") + "auth config" + "".join(f"\n  {p}" for p in problems))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
