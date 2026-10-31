"""Submit the editable Haukley App Store version (iOS or tvOS) for App Review. Updates
release to everyone at once — never a phased rollout (owner, 2026-10-17).

    ~/.venvs/marracat/bin/python iphone/scripts/submit_for_review.py --platform IOS            # dry run (GETs only)
    ~/.venvs/marracat/bin/python iphone/scripts/submit_for_review.py --platform TV_OS --submit # writes to ASC

Default is a DRY RUN: it only reads App Store Connect and prints what it would do. With
--submit it (1) removes any phased release on the version, so an approved update goes to
everyone at once; then (2) creates or reuses a review submission,
adds the version and submits it. --stage does all of that except the final submit, so another
item (an In-App Event, custom product page) can join the same review submission first; run
--submit afterwards to send it. --create VERSION --build N --whats-new TEXT creates the next
App Store version (or reuses the editable one), attaches TestFlight build N and sets the en-US
release notes. ship.sh / ios/scripts/ship_tvos.sh stay TestFlight-only;
App Store submission needs the owner's explicit go (see feedback-haukley-testflight-only).
"""
from __future__ import annotations

import argparse
import sys

import asc

EDITABLE = {"PREPARE_FOR_SUBMISSION", "DEVELOPER_REJECTED", "REJECTED", "METADATA_REJECTED"}
LIVE = {"READY_FOR_SALE", "READY_FOR_DISTRIBUTION", "REPLACED_WITH_NEW_VERSION",
        "DEVELOPER_REMOVED_FROM_SALE", "REMOVED_FROM_SALE"}


def as_paragraphs(text):
    """Release notes as short paragraphs with a blank line between them, never
    bullets (owner, 2026-10-31: "line breaks with a space in between the
    sentences instead of bullets ... do this for all our apps")."""
    import re
    if not text:
        return text
    lines = (line.strip() for line in str(text).replace("\r\n", "\n").split("\n"))
    return "\n\n".join(re.sub(r"^[•●▪◦·\-\*–]\s+", "", line) for line in lines if line)


def resolve(token, app_id, platform):
    _, d = asc.api(token, "GET", f"/apps/{app_id}/appStoreVersions",
                   {"filter[platform]": platform, "limit": 50})
    versions = d["data"]
    states = {v["attributes"]["appStoreState"] for v in versions}
    editable = next((v for v in versions if v["attributes"]["appStoreState"] in EDITABLE), None)
    return editable, bool(states & LIVE), versions


def ensure_no_phased_release(token, version, submit):
    """Release to everyone at once — never Apple's 7-day phased rollout, on
    any of our apps (owner, 2026-10-17). A phased release left on the version
    (dashboard, or an older run of this script) is deleted; one already
    rolling out is completed, which releases it to everyone."""
    vid = version["id"]
    _, have = asc.api(token, "GET", f"/appStoreVersions/{vid}/appStoreVersionPhasedRelease", ok_statuses=(404,))
    pr = have.get("data")
    if not pr:
        print("  phased release: off (releases to everyone at once)")
        return
    state = pr["attributes"]["phasedReleaseState"]
    if not submit:
        print(f"  phased release: WOULD remove ({state})")
        return
    if state in ("ACTIVE", "PAUSED"):
        asc.api(token, "PATCH", f"/appStoreVersionPhasedReleases/{pr['id']}", body={"data": {
            "type": "appStoreVersionPhasedReleases", "id": pr["id"], "attributes": {"phasedReleaseState": "COMPLETE"}}})
        print("  phased release: completed (now released to everyone)")
    else:
        asc.api(token, "DELETE", f"/appStoreVersionPhasedReleases/{pr['id']}")
        print("  phased release: removed (releases to everyone at once)")


def prepare_version(token, app_id, platform, version_string, build_number, whats_new, write):
    """Create (or reuse) the editable version, attach a processed build, set What's New."""
    version, _, _ = resolve(token, app_id, platform)
    if version and version["attributes"]["versionString"] != version_string:
        raise SystemExit(f"editable version is {version['attributes']['versionString']}, not {version_string}")
    if not version:
        if not write:
            print(f"  WOULD create {platform} version {version_string}")
            return None
        _, d = asc.api(token, "POST", "/appStoreVersions", body={"data": {
            "type": "appStoreVersions", "attributes": {"platform": platform, "versionString": version_string},
            "relationships": {"app": {"data": {"type": "apps", "id": app_id}}}}})
        version = d["data"]
        print(f"  created {platform} version {version_string}")
    _, b = asc.api(token, "GET", "/builds", {"filter[app]": app_id, "filter[version]": str(build_number),
                                               "filter[preReleaseVersion.platform]": platform, "limit": 1})
    if not b["data"]:
        raise SystemExit(f"build {build_number} not found for {platform}")
    build = b["data"][0]
    if build["attributes"].get("processingState") != "VALID":
        raise SystemExit(f"build {build_number} is {build['attributes'].get('processingState')}, not VALID yet")
    if write:
        asc.api(token, "PATCH", f"/appStoreVersions/{version['id']}/relationships/build",
                body={"data": {"type": "builds", "id": build["id"]}})
        _, loc = asc.api(token, "GET", f"/appStoreVersions/{version['id']}/appStoreVersionLocalizations")
        en = next(l for l in loc["data"] if l["attributes"]["locale"] == "en-US")
        asc.api(token, "PATCH", f"/appStoreVersionLocalizations/{en['id']}", body={"data": {
            "type": "appStoreVersionLocalizations", "id": en["id"], "attributes": {"whatsNew": as_paragraphs(whats_new)}}})
    print(f"  {'attached' if write else 'WOULD attach'} build {build_number}; What's New: {whats_new!r}")
    return version


def submit_version(token, app_id, platform, version, final=True):
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
    if not final:
        _, items = asc.api(token, "GET", f"/reviewSubmissions/{draft['id']}/items")
        print(f"  STAGED: review submission {draft['id']} is READY_FOR_REVIEW with {len(items['data'])} item(s);"
              " add other items now, then rerun with --submit")
        return
    _, d = asc.api(token, "PATCH", f"/reviewSubmissions/{draft['id']}", body={"data": {
        "type": "reviewSubmissions", "id": draft["id"], "attributes": {"submitted": True}}})
    print("  submission state:", d["data"]["attributes"]["state"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", choices=["IOS", "TV_OS"], required=True)
    ap.add_argument("--submit", action="store_true", help="actually write to App Store Connect")
    ap.add_argument("--stage", action="store_true", help="write everything but the final submit")
    ap.add_argument("--create", metavar="VERSION", help="create/reuse this App Store version")
    ap.add_argument("--build", type=int, help="TestFlight build number to attach (with --create)")
    ap.add_argument("--whats-new", help="en-US release notes (with --create)")
    a = ap.parse_args()
    cfg = asc.load_config()
    token = asc.make_token(cfg)
    app_id = cfg.get("ASC_APP_ID") or "6815405240"
    write = a.submit or a.stage
    if a.create:
        if not (a.build and a.whats_new):
            raise SystemExit("--create needs --build and --whats-new")
        lowered = a.whats_new.lower()
        if "free" in lowered.split() or "$" in lowered:
            raise SystemExit("no price words in release notes (guideline 2.3.7)")
        prepare_version(token, app_id, a.platform, a.create, a.build, a.whats_new, write)
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
    ensure_no_phased_release(token, version, write)
    if not write:
        print("dry run - nothing written; rerun with --stage / --submit (owner's explicit go only)")
        return 0
    submit_version(token, app_id, a.platform, version, final=a.submit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
