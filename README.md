# StreamTV

Apple TV–style streaming app prototype for TV platforms, built with
[react-native-tvos](https://github.com/react-native-tvos/react-native-tvos).
One codebase runs on **Fire TV (Fire OS)**, **Android TV / Google TV**, and **Apple TV (tvOS)**.

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
