# Haukley for LG (webOS) and Samsung (Tizen) TVs

One vanilla-JS TV web app (`src/`) packaged two ways:

| | LG webOS | Samsung Tizen |
|---|---|---|
| Package | `dist/com.haukley.tv_1.0.0_all.ipk` | `dist/Haukley-1.0.0-unsigned.wgt` (must be signed, below) |
| Manifest | `webos/appinfo.json` (id `com.haukley.tv`) | `tizen/config.xml` (package `HaukleyTV0`, app id `HaukleyTV0.Haukley`, `required_version` 6.0 = 2021+ TVs) |
| Back key | keyCode 461 (`disableBackHistoryAPI: true`) | keyCode 10009 |
| Ad events platform | `lg` | `samsung` (migration 0011) |

Same catalog, rows and per-title VMAP ad schedule as every other Haukley app: the live
catalog `https://haukley.com/watch/catalog/catalog.json` (CORS `*`, nginx) with the packaged
`catalog.json` as the offline fallback; art from `haukley.com/watch/catalog/<id>/`; HLS from the
DigitalOcean CDN played natively by the TV's `<video>` (hls.js only kicks in on desktop
browsers); Google IMA HTML5 SDK for ads. Screens: Home (hero + rows + Continue Watching),
Movies (all titles by genre), Search (on-screen keyboard), title page, player. Back on Home
asks "Exit Haukley?" (a certification requirement on both stores). JS is kept to ES2016
syntax and the CSS avoids flex `gap`/grid/`inset` so 2018+ webOS (Chromium 53) runs it.

## Build and test

```bash
.venv/bin/python tvweb/make_assets.py                 # icons + splash (+ store art)
tvweb/build.sh                                        # -> tvweb/dist/*.ipk, *.wgt
~/.venvs/dhcr-map/bin/python tvweb/test_journey.py    # remote-only journey in Chrome 1920x1080
.venv/bin/python tvweb/make_assets.py --shots tvweb/dist/journey   # store screenshots
```

Bump the version in BOTH `webos/appinfo.json` and `tizen/config.xml` for every store update.

## Store images (in `marketing/lg/` and `marketing/samsung/`)

LG Seller Lounge:
- App icon 400x400 PNG, square — `icon-400x400.png` ([webOS TV app resources][lg-res])
- Package icons 80x80 + 130x130 PNG, splash 1920x1080 PNG, not black — in `webos/` ([appinfo.json reference][lg-appinfo], [app resources][lg-res])
- Screenshots 1280x720 (or 960x540): 1 primary + 2–5 secondary — `screenshot-1..6-1280x720.png`
- Launcher background + splash background 1920x1080 — `launcher-bg-1920x1080.png`, `splash-1920x1080.png` ([Brightcove's LG submission walkthrough][bc-lg], which mirrors the Seller Lounge form)

Samsung Seller Office ([Entering Application Information][ss-info]):
- Icon 1920x1080, transparent 32-bit PNG (RGBA), ≤300 KB — `icon-1920x1080.png`
- Icon 512x423 PNG, ≤300 KB — `icon-512x423.png`
- Exactly 4 screenshots, 1920x1080 JPG, ≤500 KB each — `screenshot-1..4-1920x1080.jpg`

## What the owner does

### LG (LG Seller Lounge)
1. Create an LG account, then join Seller Lounge: https://seller.lgappstv.com (Sign up → choose
   individual or corporate; there is no fee).
2. APP MANAGEMENT → Register App. App ID/name "Haukley", platform **webOS TV**, upload
   `com.haukley.tv_1.0.0_all.ipk`, resolution **1920x1080 (FHD)**.
3. Images: upload the files in `marketing/lg/` (icon 400x400, tile color `#2b1a55`, screenshots,
   launcher + splash backgrounds).
4. Service info: category **Entertainment / Movies**, countries **United States only** (the films
   are public domain in the US), age rating (the catalog includes classic horror/war films —
   answer the questionnaire honestly), support email hello@haukley.com, privacy policy
   https://haukley.com/privacy.
5. Test info: download and fill LG's self-checklist + UX scenario templates from that page; say
   "no login, free, ad-supported; Back on Home shows an exit dialog".
6. Submit. LG QA typically takes 5–10 business days ([Brightcove][bc-lg]).

### Samsung (Seller Office)
1. Create a Samsung account and register at https://seller.samsungapps.com/tv (public seller;
   public sellers can launch in the **US only**, which matches our rights — [ss-info]).
2. Sign the package (one-time setup, needs your Samsung account):
   - Install Tizen Studio + the "Samsung Certificate Extension" (Package Manager → Extension SDK).
   - Tools → Certificate Manager → **+** → **Samsung** → TV → create an **author** certificate
     (log in with the Samsung account) and a **distributor** certificate (Public level).
     Back up the author `.p12` and its password — every future update must use the same one
     ([Tizen Studio Q&A][ss-faq]).
   - Sign: `tizen package -t wgt -s <profile> -- tvweb/dist/tizen` (or Tizen Studio's
     *Build Signed Package*), which produces a signed `Haukley.wgt`.
   Or send the certificate profile to Claude and it can run the signing step.
3. Applications → Create: title "Haukley", type **Tizen Web**, default language English (US).
4. Upload the signed `.wgt`; the pre-test runs automatically and must pass.
5. Information: icons + 4 screenshots from `marketing/samsung/`, description, ≥3 keywords
   (free movies, classic films, silent films), category **Videos**, billing **Free**,
   privacy policy https://haukley.com/privacy, support hello@haukley.com.
6. Request release; Samsung runs its verification test and reports defects if any.

## Known gaps
- Not yet run on real LG/Samsung hardware or their emulators (needs the webOS TV simulator /
  Tizen TV emulator, or a TV in developer mode). The journey test runs in desktop Chrome.
- Ads: the VMAP currently resolves to whatever `scripts/make_vmap.py` publishes; when the Google
  Ad Manager tag replaces it, nothing in this app changes.
- Samsung "In-app AD" apps are expected to declare the `adinfo` privilege (done) and may be asked
  to pass the TV's TIFA advertising ID to the ad server — not wired yet.

[lg-appinfo]: https://webostv.developer.lge.com/develop/references/appinfo-json
[lg-res]: https://webostv.developer.lge.com/develop/getting-started/app-resources
[bc-lg]: https://beacon-help.support.brightcove.com/publishing-apps/lg/submitting-to-lg.html
[ss-info]: https://developer.samsung.com/tv-seller-office/guides/applications/entering-application-information.html
[ss-faq]: https://developer.samsung.com/smarttv/develop/faq/tizen-studio.html
