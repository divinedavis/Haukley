"""Apply the Haukley App Store listing text (iOS + tvOS) and swap single screenshots.

    ~/.venvs/marracat/bin/python iphone/scripts/asc_listing.py text            # dry run
    ~/.venvs/marracat/bin/python iphone/scripts/asc_listing.py text --apply
    ~/.venvs/marracat/bin/python iphone/scripts/asc_listing.py screenshot TV_OS player.png marketing/appletv/player.png --apply
    ~/.venvs/marracat/bin/python iphone/scripts/asc_listing.py drop-screenshot IOS APP_IPAD_PRO_3GEN_129 05-rows.png --apply

Rules learned from App Review (2026-10-02, tvOS 1.0 build 3):
- 2.3.7: no price words in the subtitle, keywords or promo text — "free" counts. Price talk
  belongs in the description only.
- 4.1(a): third-party characters (Big Buck Bunny, Sintel, Sprite Fright…) in screenshots or
  copy read as copycat content even when CC BY. Show public-domain titles only.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from asc import api, load_config, make_token  # noqa: E402

PRICE_WORDS = ("free", "$", "discount", "sale", "no cost", "price")
THIRD_PARTY = ("big buck bunny", "sintel", "sprite fright", "caminandes", "spring")

SUBTITLE = "Silent films, noir & classics"
KEYWORDS = "classic movies,classic films,old movies,film noir,silent film,horror,westerns,black and white,cinema"
PROMO = "64 classic films: silent comedy, film noir, horror, westerns and more."

_FILMS = """Watch 64 films, from silent comedy to film noir:

• Silent comedy legends — Buster Keaton's The General, Sherlock Jr. and Steamboat Bill, Jr.; Harold Lloyd's Safety Last!
• Classic horror — Nosferatu, Night of the Living Dead, Carnival of Souls, The Phantom of the Opera
• Film noir and crime — D.O.A., Scarlet Street, The Hitch-Hiker, The Big Combo
• Swashbucklers, westerns and war epics — The Mark of Zorro, The Black Pirate, The Big Trail, Wings
• Landmarks of cinema — Metropolis, Sunrise, A Trip to the Moon, Man with a Movie Camera"""

_FOOTER = """Haukley is supported by ads. Every film on Haukley is in the U.S. public domain or released under a Creative Commons license.

Questions? hello@haukley.com"""

DESCRIPTION = {
    "IOS": f"""Haukley is free streaming for classic movies. No subscription, no credit card — open the app and press play.

{_FILMS}

What you get:
• Profiles for everyone in the house, including Kids profiles
• Continue Watching picks up where you left off
• My List to save films for later
• Clips: a quick vertical feed of scenes to help you find something to watch
• Search by title, genre or year

{_FOOTER}""",
    "TV_OS": f"""Haukley is free streaming for classic movies on your Apple TV. No subscription, no credit card — open the app and press play.

{_FILMS}

Browse by row with the Siri Remote, and Continue Watching picks up where you left off.

{_FOOTER}""",
}


def lint() -> list[str]:
    """Problems App Review has rejected before; empty list = clean."""
    errs = []
    if len(SUBTITLE) > 30:
        errs.append(f"subtitle is {len(SUBTITLE)} chars (max 30)")
    if len(KEYWORDS) > 100:
        errs.append(f"keywords are {len(KEYWORDS)} chars (max 100)")
    for name, text in (("subtitle", SUBTITLE), ("keywords", KEYWORDS), ("promo", PROMO)):
        low = text.lower()
        errs += [f"{name} mentions price word {w!r} (2.3.7)" for w in PRICE_WORDS if w in low]
    for name, text in [("subtitle", SUBTITLE), ("keywords", KEYWORDS), ("promo", PROMO), *DESCRIPTION.items()]:
        low = text.lower()
        errs += [f"{name} names third-party title {w!r} (4.1)" for w in THIRD_PARTY if w in low]
    return errs


def _app_id(cfg: dict) -> str:
    return cfg.get("ASC_APP_ID") or "6815405240"


def _version(t: str, app: str, platform: str) -> dict:
    _, d = api(t, "GET", f"/apps/{app}/appStoreVersions", {"filter[platform]": platform, "limit": 5})
    live = [v for v in d["data"] if v["attributes"]["appStoreState"] != "READY_FOR_SALE"]
    if not live:
        raise SystemExit(f"no editable {platform} version")
    return live[0]


def _localization(t: str, version_id: str) -> dict:
    _, d = api(t, "GET", f"/appStoreVersions/{version_id}/appStoreVersionLocalizations")
    return next(l for l in d["data"] if l["attributes"]["locale"] == "en-US")


def apply_text(t: str, app: str, do: bool) -> None:
    _, infos = api(t, "GET", f"/apps/{app}/appInfos")
    for info in infos["data"]:
        _, locs = api(t, "GET", f"/appInfos/{info['id']}/appInfoLocalizations")
        for loc in locs["data"]:
            print(f"subtitle {loc['attributes']['subtitle']!r} -> {SUBTITLE!r}")
            if do:
                api(t, "PATCH", f"/appInfoLocalizations/{loc['id']}", body={"data": {
                    "type": "appInfoLocalizations", "id": loc["id"], "attributes": {"subtitle": SUBTITLE}}})
    for platform, desc in DESCRIPTION.items():
        v = _version(t, app, platform)
        loc = _localization(t, v["id"])
        print(f"{platform} {v['attributes']['versionString']} ({v['attributes']['appStoreState']}): keywords, promo, description")
        if do:
            api(t, "PATCH", f"/appStoreVersionLocalizations/{loc['id']}", body={"data": {
                "type": "appStoreVersionLocalizations", "id": loc["id"],
                "attributes": {"keywords": KEYWORDS, "promotionalText": PROMO, "description": desc}}})


def _screenshot_set(t: str, app: str, platform: str, display_type: str | None) -> tuple[dict, list[dict]]:
    v = _version(t, app, platform)
    loc = _localization(t, v["id"])
    _, sets = api(t, "GET", f"/appStoreVersionLocalizations/{loc['id']}/appScreenshotSets")
    s = next(s for s in sets["data"]
             if display_type is None or s["attributes"]["screenshotDisplayType"] == display_type)
    _, shots = api(t, "GET", f"/appScreenshotSets/{s['id']}/appScreenshots")
    return s, shots["data"]


def replace_screenshot(t: str, app: str, platform: str, file_name: str, path: pathlib.Path, do: bool) -> None:
    s, shots = _screenshot_set(t, app, platform, "APP_APPLE_TV" if platform == "TV_OS" else None)
    old = next(x for x in shots if x["attributes"]["fileName"] == file_name)
    order = [x["id"] for x in shots]
    print(f"{s['attributes']['screenshotDisplayType']}: replace {file_name} (slot {order.index(old['id']) + 1}) with {path}")
    if not do:
        return
    data = path.read_bytes()
    _, new = api(t, "POST", "/appScreenshots", body={"data": {
        "type": "appScreenshots",
        "attributes": {"fileName": file_name, "fileSize": len(data)},
        "relationships": {"appScreenshotSet": {"data": {"type": "appScreenshotSets", "id": s["id"]}}}}})
    for op in new["data"]["attributes"]["uploadOperations"]:
        chunk = data[op["offset"]: op["offset"] + op["length"]]
        hdrs = {h["name"]: h["value"] for h in op["requestHeaders"]}
        requests.request(op["method"], op["url"], headers=hdrs, data=chunk, timeout=120).raise_for_status()
    api(t, "PATCH", f"/appScreenshots/{new['data']['id']}", body={"data": {
        "type": "appScreenshots", "id": new["data"]["id"],
        "attributes": {"uploaded": True, "sourceFileChecksum": hashlib.md5(data).hexdigest()}}})
    api(t, "DELETE", f"/appScreenshots/{old['id']}")
    order[order.index(old["id"])] = new["data"]["id"]
    api(t, "PATCH", f"/appScreenshotSets/{s['id']}/relationships/appScreenshots",
        body={"data": [{"type": "appScreenshots", "id": i} for i in order]})
    print("  uploaded", new["data"]["id"])


def drop_screenshot(t: str, app: str, platform: str, display_type: str, file_name: str, do: bool) -> None:
    s, shots = _screenshot_set(t, app, platform, display_type)
    old = next(x for x in shots if x["attributes"]["fileName"] == file_name)
    print(f"{display_type}: delete {file_name} ({len(shots) - 1} left)")
    if do:
        api(t, "DELETE", f"/appScreenshots/{old['id']}")


def main(argv: list[str]) -> None:
    do = "--apply" in argv
    args = [a for a in argv if a != "--apply"]
    if not args:
        raise SystemExit(__doc__)
    errs = lint()
    if errs:
        raise SystemExit("listing lint failed:\n  " + "\n  ".join(errs))
    cfg = load_config()
    t, app = make_token(cfg), _app_id(cfg)
    if args[0] == "text":
        apply_text(t, app, do)
    elif args[0] == "screenshot":
        replace_screenshot(t, app, args[1], args[2], pathlib.Path(args[3]), do)
    elif args[0] == "drop-screenshot":
        drop_screenshot(t, app, args[1], args[2], args[3], do)
    else:
        raise SystemExit(__doc__)
    if not do:
        print("(dry run — add --apply)")


if __name__ == "__main__":
    main(sys.argv[1:])
