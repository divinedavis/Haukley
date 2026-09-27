#!/usr/bin/env bash
# Haukley Apple TV — bump build, archive, export, upload to TestFlight.
#
# TESTFLIGHT ONLY: never creates, attaches to or submits an App Store version. The Apple TV
# app shares the iPhone app's App Store Connect record (com.haukley.app, app 6815405240) and
# its API key (iphone/scripts/asc-config.env).
#
#   ios/scripts/ship_tvos.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
source ../iphone/scripts/asc-config.env

PBX=StreamTV.xcodeproj/project.pbxproj
current=$(grep -m1 'CURRENT_PROJECT_VERSION = ' "$PBX" | sed -E 's/.*= ([0-9]+);/\1/')
next=$((current + 1))
echo "==> bumping tvOS build $current -> $next"
sed -i '' "s/CURRENT_PROJECT_VERSION = $current;/CURRENT_PROJECT_VERSION = $next;/g" "$PBX"

AUTH=(-authenticationKeyPath "$ASC_KEY_PATH" -authenticationKeyID "$ASC_KEY_ID"
      -authenticationKeyIssuerID "$ASC_ISSUER_ID")

echo "==> archiving"
rm -rf build/release
xcodebuild -workspace StreamTV.xcworkspace -scheme StreamTV -configuration Release \
    -destination "generic/platform=tvOS" -archivePath build/release/Haukley-tvOS.xcarchive \
    DEVELOPMENT_TEAM="$ASC_TEAM_ID" CODE_SIGN_STYLE=Manual CODE_SIGN_IDENTITY="Apple Distribution" \
    PROVISIONING_PROFILE_SPECIFIER="Haukley tvOS App Store" -quiet archive
# Manual distribution signing: automatic signing wants a tvOS *development* profile, which
# needs a registered Apple TV device. The App Store profile (created via the ASC API, cert
# "Apple Distribution: Divine Davis") needs none.

echo "==> exporting IPA"
xcodebuild -exportArchive -archivePath build/release/Haukley-tvOS.xcarchive \
    -exportPath build/release/export -exportOptionsPlist scripts/ExportOptions-tvos.plist

IPA=$(ls build/release/export/*.ipa | head -1)
if [[ "${SHIP_NO_UPLOAD:-0}" == "1" ]]; then
    echo "==> SHIP_NO_UPLOAD=1 — built $IPA, not uploading"; exit 0
fi

echo "==> uploading to TestFlight"
xcrun altool --upload-app -f "$IPA" -t appletvos --apiKey "$ASC_KEY_ID" --apiIssuer "$ASC_ISSUER_ID"
echo "==> shipped tvOS build $next to TestFlight (App Store untouched). Apple takes a few minutes to process it."
