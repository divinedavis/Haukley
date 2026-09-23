# StreamTV

Apple TV–style streaming app prototype for TV platforms, built with
[react-native-tvos](https://github.com/react-native-tvos/react-native-tvos).
One codebase runs on **Fire TV (Fire OS)**, **Android TV / Google TV**, and **Apple TV (tvOS)**.
**Roku** has its own BrightScript/SceneGraph app in `roku/`, built from the same catalog and art.

All titles, posters and people are fictional. Photos are from Picsum (Unsplash License),
poster type uses open-license Google Fonts, and playback uses public HLS test streams.

## Run it

```bash
npm install

# Fire TV over Wi-Fi ADB (Developer Options → ADB debugging on the TV)
scripts/firetv.sh 192.168.1.155

# Apple TV simulator
cd ios && bundle install && bundle exec pod install && cd ..
xcodebuild -workspace ios/StreamTV.xcworkspace -scheme StreamTV -configuration Release \
  -sdk appletvsimulator -derivedDataPath ios/build CODE_SIGNING_ALLOWED=NO build
```

## Roku

```bash
.venv/bin/python scripts/make_roku.py   # -> roku/dist/StreamTV-roku.zip (must stay under Roku's 4 MB cap)
```

Row lineup and streams live in `scripts/rows.json`, shared with the React Native app.

Install on a Roku without a developer account (sideload):
1. On the Roku remote press **Home ×3, Up ×2, Right, Left, Right, Left, Right**, accept the agreement, set a password, and note the IP shown.
2. On a computer on the same Wi-Fi, open `http://<roku-ip>`, sign in as `rokudev` with that password.
3. Upload `StreamTV-roku.zip` and click **Install with zip**.

A Roku beta app (invite link, up to 20 testers) needs a signed `.pkg`, which can only be made on a real
Roku in developer mode (`genkey`, then the Packager page at `http://<roku-ip>`).

Emulator check: `brs-node` (`npx brs-cli -e -s snap.png roku/dist/StreamTV-roku.zip`) runs the SceneGraph UI
and takes ECP key presses. It has no video output, so playback only shows on a real Roku.

Roku gotchas: the emulator ignores `font:BoldSystemFontFile` at custom sizes, so the app bundles Poppins
(OFL) in `roku/fonts`; `scaleToZoom` crops the pre-faded backdrops, so posters use `scaleToFill`.

## Art

`scripts/catalog.json` is the source of truth for titles. Regenerate posters, cards,
backdrops and episode stills with:

```bash
python3 -m venv .venv && .venv/bin/pip install pillow requests
.venv/bin/python scripts/make_posters.py
```

## Fire OS gotchas (found on a Toshiba Fire TV, Fire OS 7)

- Bundled images must be `@2x` or Android upscales them 2x on 320dpi TVs and runs out of bitmap memory.
- Gradient overlay PNGs didn't render; fades are baked into the backdrops instead.
- Native-driven opacity animations stall after a view is hidden; the hero fade uses the JS driver.
- Video renders on a hardware plane, so `adb screencap` shows black during playback.
