#!/usr/bin/env bash
# Haukley iPhone — smoke launch, UI tests, bump build, archive, export, upload to TestFlight.
#
# TESTFLIGHT ONLY: this stops after the upload and the internal tester group. It never
# creates an App Store version, attaches a build to one, or submits for review — the owner
# will say explicitly when the app may go to the App Store.
#
#   SIM_UDID=<free iPhone simulator> iphone/scripts/ship.sh
#   SHIP_SKIP_TESTS=1 iphone/scripts/ship.sh     # smoke launch only
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PY:-$HOME/.venvs/marracat/bin/python}"
# shellcheck disable=SC1091
source scripts/asc-config.env
if [[ -z "${ASC_APP_ID:-}" ]]; then
    echo "error: ASC_APP_ID is empty — create the app record, then run scripts/register_in_asc.py" >&2
    exit 1
fi

ICON=Haukley/Resources/Assets.xcassets/AppIcon.appiconset/icon-1024.png
if sips -g hasAlpha "$ICON" | grep -q "hasAlpha: yes"; then
    echo "error: $ICON has an alpha channel — App Store validation rejects it" >&2
    exit 1
fi

export SIM_UDID="${SIM_UDID:-$(xcrun simctl list devices available | awk -F'[()]' '/iPhone 17 Pro \(/ {print $2; exit}')}"

echo "==> smoke-testing a cold launch on $SIM_UDID"
./scripts/smoke_test.sh

# xcodebuild prints an "Executed" summary per test class and per bundle, so one green
# class line (e.g. the skipped screenshot class) proves nothing. Pass only if some line
# ran at least one test and NO line reports a failure.
ui_tests_passed() {
    grep -qE "Executed [1-9][0-9]* tests?, with " "$1" &&
        ! grep -E "Executed [0-9]+ tests?, with " "$1" | grep -qE "with ([0-9]+ tests? skipped and )?[1-9][0-9]* failures?"
}

if [[ "${SHIP_SKIP_TESTS:-0}" != "1" ]]; then
    echo "==> UI tests"
    log=$(mktemp)
    xcodebuild -project Haukley.xcodeproj -scheme Haukley \
        -destination "platform=iOS Simulator,id=$SIM_UDID" -derivedDataPath build/smoke \
        -retry-tests-on-failure -test-iterations 2 test 2>&1 | tee "$log" | grep -E "Test Case .*(passed|failed)|Executed" || true
    # xcodebuild can "succeed" with zero tests run; ui_tests_passed requires the count.
    if ! ui_tests_passed "$log"; then
        echo "error: UI tests failed or none ran" >&2; exit 1
    fi
    # The app is universal: run the same suite on an iPad (11-inch) too.
    IPAD_UDID="${IPAD_UDID:-$(xcrun simctl list devices available | grep 'iPad Air 11-inch (M4)' | grep -oE '[0-9A-F-]{36}' | head -1)}"
    echo "==> UI tests on iPad ($IPAD_UDID)"
    xcodebuild -project Haukley.xcodeproj -scheme Haukley \
        -destination "platform=iOS Simulator,id=$IPAD_UDID" -derivedDataPath build/smoke-ipad \
        -retry-tests-on-failure -test-iterations 2 test 2>&1 | tee "$log" | grep -E "Test Case .*(passed|failed)|Executed" || true
    if ! ui_tests_passed "$log"; then
        echo "error: iPad UI tests failed or none ran" >&2; exit 1
    fi
fi

current=$(grep -m1 'CURRENT_PROJECT_VERSION:' project.yml | sed -E 's/.*"([0-9]+)".*/\1/')
next=$((current + 1))
echo "==> bumping build $current -> $next"
sed -i '' "s/CURRENT_PROJECT_VERSION: \"$current\"/CURRENT_PROJECT_VERSION: \"$next\"/" project.yml
xcodegen generate --quiet

AUTH=(-authenticationKeyPath "$ASC_KEY_PATH" -authenticationKeyID "$ASC_KEY_ID"
      -authenticationKeyIssuerID "$ASC_ISSUER_ID")

echo "==> archiving"
rm -rf build/release
xcodebuild -project Haukley.xcodeproj -scheme Haukley -configuration Release \
    -destination "generic/platform=iOS" -archivePath build/release/Haukley.xcarchive \
    -allowProvisioningUpdates "${AUTH[@]}" DEVELOPMENT_TEAM="$ASC_TEAM_ID" -quiet archive

echo "==> exporting IPA"
xcodebuild -exportArchive -archivePath build/release/Haukley.xcarchive \
    -exportPath build/release/export -exportOptionsPlist ExportOptions.plist \
    -allowProvisioningUpdates "${AUTH[@]}"

if [[ "${SHIP_NO_UPLOAD:-0}" == "1" ]]; then
    echo "==> SHIP_NO_UPLOAD=1 — built build/release/export/Haukley.ipa, not uploading"; exit 0
fi

echo "==> uploading to TestFlight"
xcrun altool --upload-app -f build/release/export/Haukley.ipa -t ios \
    --apiKey "$ASC_KEY_ID" --apiIssuer "$ASC_ISSUER_ID"

echo "==> internal TestFlight group"
"$PY" scripts/configure_internal_testers.py

echo "==> shipped build $next to TestFlight (App Store untouched). Apple takes a few minutes to process it."
