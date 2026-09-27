#!/bin/bash
# Build the LG webOS (.ipk) and Samsung Tizen (.wgt) packages from tvweb/src.
#   dist/webos/                  unpacked webOS app      -> dist/com.haukley.tv_<ver>_all.ipk
#   dist/tizen/                  unpacked Tizen widget   -> dist/Haukley-<ver>-unsigned.wgt
# The packaged catalog.json is the fallback when the live catalog can't be fetched; it comes
# from web/watch/catalog/catalog.json (scripts/make_web.py), so run that first after catalog changes.
# The Tizen package must be signed with the Samsung author + distributor certificates before
# it can be installed or uploaded; see README.md.
set -euo pipefail
cd "$(dirname "$0")"
VERSION=$(python3 -c 'import json; print(json.load(open("webos/appinfo.json"))["version"])')
grep -q "version=\"$VERSION\"" tizen/config.xml || { echo "tizen/config.xml version != $VERSION"; exit 1; }

rm -rf dist && mkdir -p dist/webos dist/tizen
for d in dist/webos dist/tizen; do
  cp -R src/. "$d/"
  cp ../web/watch/catalog/catalog.json "$d/catalog.json"
done
cp webos/appinfo.json webos/icon.png webos/largeIcon.png webos/splash.png dist/webos/
cp tizen/config.xml tizen/icon.png dist/tizen/
find dist -name .DS_Store -delete

npx -y -p @webos-tools/cli@3 ares-package dist/webos -o dist --no-minify >/dev/null
IPK=$(ls dist/*.ipk)

(cd dist/tizen && rm -f "../Haukley-$VERSION-unsigned.wgt" && zip -qr -X "../Haukley-$VERSION-unsigned.wgt" .)
echo "built $IPK ($(du -h "$IPK" | cut -f1)) and dist/Haukley-$VERSION-unsigned.wgt ($(du -h "dist/Haukley-$VERSION-unsigned.wgt" | cut -f1))"
