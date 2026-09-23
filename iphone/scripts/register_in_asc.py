#!/usr/bin/env python3
"""Register the Haukley bundle ID and capture the App Store Connect app id.

Idempotent. The ASC API cannot create app records (/apps is GET + UPDATE only),
so the first run registers com.haukley.app and prints the exact values to type
into App Store Connect -> + -> New App. Re-run afterwards to save ASC_APP_ID.

TestFlight only: nothing here creates an App Store version or submits anything.

Usage:
    ~/.venvs/marracat/bin/python iphone/scripts/register_in_asc.py
"""
from __future__ import annotations

from asc import api, load_config, make_token, write_config_value

APP_NAME = "Haukley"
SKU = "haukley-001"


def main() -> None:
    cfg = load_config()
    bundle = cfg["ASC_BUNDLE_ID"]
    token = make_token(cfg)

    print(f"==> bundle id {bundle}")
    _, res = api(token, "GET", "/bundleIds", params={"filter[identifier]": bundle, "limit": 1})
    if res.get("data"):
        print(f"   already registered (resource id {res['data'][0]['id']})")
    else:
        _, res = api(token, "POST", "/bundleIds", body={"data": {
            "type": "bundleIds",
            "attributes": {"identifier": bundle, "name": APP_NAME, "platform": "IOS"},
        }})
        print(f"   registered (resource id {res['data']['id']})")

    print("==> App Store Connect app record")
    _, res = api(token, "GET", "/apps", params={"filter[bundleId]": bundle, "limit": 1})
    if not res.get("data"):
        print("   not created yet — Apple only allows this in the dashboard:")
        print("     https://appstoreconnect.apple.com/apps  ->  +  ->  New App")
        print("     Platforms  iOS (tvOS can be added to the same record later)")
        print(f"     Name       {APP_NAME}")
        print("     Language   English (U.S.)")
        print(f"     Bundle ID  {bundle}")
        print(f"     SKU        {SKU}")
        print("     Access     Full Access")
        print("   then re-run this script.")
        raise SystemExit(2)

    app = res["data"][0]
    write_config_value("ASC_APP_ID", app["id"])
    print(f"   found '{app['attributes']['name']}' (app id {app['id']}) -> saved ASC_APP_ID")


if __name__ == "__main__":
    main()
