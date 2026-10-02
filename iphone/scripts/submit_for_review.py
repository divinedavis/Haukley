"""Submit the editable Haukley App Store version (iOS or tvOS) for App Review, with a
7-day phased release on every update.

    ~/.venvs/marracat/bin/python iphone/scripts/submit_for_review.py --platform IOS            # dry run (GETs only)
    ~/.venvs/marracat/bin/python iphone/scripts/submit_for_review.py --platform TV_OS --submit # writes to ASC

Default is a DRY RUN: it only reads App Store Connect and prints what it would do. With
--submit it (1) attaches an INACTIVE phased release to the version, so an approved update
rolls out over Apple's 7 days and can be paused if it crashes (App Store Connect > the
version > Phased Release); Apple only offers this for updates, so it is skipped while the
platform has never had a version on sale; then (2) creates or reuses a review submission,
adds the version and submits it. ship.sh / ios/scripts/ship_tvos.sh stay TestFlight-only;
App Store submission needs the owner's explicit go (see feedback-haukley-testflight-only).
"""
from __future__ import annotations

import argparse
import sys

import asc

EDITABLE = {"PREPARE_FOR_SUBMISSION", "DEVELOPER_REJECTED", "REJECTED", "METADATA_REJECTED"}
LIVE = {"READY_FOR_SALE", "READY_FOR_DISTRIBUTION", "REPLACED_WITH_NEW_VERSION",
        "DEVELOPER_REMOVED_FROM_SALE", "REMOVED_FROM_SALE"}


def resolve(token, app_id, platform):
    _, d = asc.api(token, "GET", f"/apps/{app_id}/appStoreVersions",
                   {"filter[platform]": platform, "limit": 50})
    versions = d["data"]
    states = {v["attributes"]["appStoreState"] for v in versions}
    editable = next((v for v in versions if v["attributes"]["appStoreState"] in EDITABLE), None)
    return editable, bool(states & LIVE), versions


def ensure_phased_release(token, version, has_live_version, submit):
    """INACTIVE phased release on the version; Apple flips it ACTIVE on release."""
    vid, vs = version["id"], version["attributes"]["versionString"]
    if not has_live_version:
        print(f"  phased release: skipped ({vs} would be the first release on this platform)")
        return
    _, have = asc.api(token, "GET", f"/appStoreVersions/{vid}/appStoreVersionPhasedRelease", ok_statuses=(404,))
    if have.get("data"):
        print("  phased release:", have["data"]["attributes"]["phasedReleaseState"])
        return
    if not submit:
        print("  phased release: WOULD create (INACTIVE, 7-day rollout once approved)")
        return
    asc.api(token, "POST", "/appStoreVersionPhasedReleases", body={"data": {
        "type": "appStoreVersionPhasedReleases", "attributes": {"phasedReleaseState": "INACTIVE"},
        "relationships": {"appStoreVersion": {"data": {"type": "appStoreVersions", "id": vid}}}}})
    print("  phased release: on (7-day rollout once approved)")


def submit_version(token, app_id, platform, version):
    _, d = asc.api(token, "GET", "/reviewSubmissions",
                   {"filter[app]": app_id, "filter[platform]": platform, "limit": 10})
    subs = d["data"]
    if any(s["attributes"]["state"] == "UNRESOLVED_ISSUES" for s in subs):
        raise SystemExit("a submission is in UNRESOLVED_ISSUES (a rejection): answer it in App Store Connect first")
    draft = next((s for s in subs if s["attributes"]["state"] == "READY_FOR_REVIEW"), None)
    if not draft:
        _, d = asc.api(token, "POST", "/reviewSubmissions", body={"data": {
            "type": "reviewSubmissions", "attributes": {"platform": platform},
            "relationships": {"app": {"data": {"type": "apps", "id": app_id}}}}})
        draft = d["data"]
    _, items = asc.api(token, "GET", f"/reviewSubmissions/{draft['id']}/items", {"include": "appStoreVersion"})
    if not any((i["relationships"].get("appStoreVersion", {}).get("data") or {}).get("id") == version["id"]
               for i in items["data"]):
        asc.api(token, "POST", "/reviewSubmissionItems", body={"data": {"type": "reviewSubmissionItems", "relationships": {
            "reviewSubmission": {"data": {"type": "reviewSubmissions", "id": draft["id"]}},
            "appStoreVersion": {"data": {"type": "appStoreVersions", "id": version["id"]}}}}})
    _, d = asc.api(token, "PATCH", f"/reviewSubmissions/{draft['id']}", body={"data": {
        "type": "reviewSubmissions", "id": draft["id"], "attributes": {"submitted": True}}})
    print("  submission state:", d["data"]["attributes"]["state"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", choices=["IOS", "TV_OS"], required=True)
    ap.add_argument("--submit", action="store_true", help="actually write to App Store Connect")
    a = ap.parse_args()
    cfg = asc.load_config()
    token = asc.make_token(cfg)
    app_id = cfg.get("ASC_APP_ID") or "6815405240"
    version, has_live, versions = resolve(token, app_id, a.platform)
    for v in versions:
        print(f"  {a.platform} {v['attributes']['versionString']}: {v['attributes']['appStoreState']}")
    if not version:
        print("no editable version (PREPARE_FOR_SUBMISSION / rejected) - nothing to submit")
        return 0 if not a.submit else 1
    vs = version["attributes"]["versionString"]
    _, b = asc.api(token, "GET", f"/appStoreVersions/{version['id']}/build")
    build = (b.get("data") or {}).get("attributes", {}).get("version")
    print(f"==> {a.platform} {vs} (build {build or 'NONE ATTACHED'})")
    if not build:
        raise SystemExit("attach a build to the version first")
    ensure_phased_release(token, version, has_live, a.submit)
    if not a.submit:
        print("dry run - nothing written; rerun with --submit (owner's explicit go only)")
        return 0
    submit_version(token, app_id, a.platform, version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
