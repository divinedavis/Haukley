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
IPAD_UDID="${IPAD_UDID:-$(xcrun simctl list devices available | grep 'iPad Air 11-inch (M4)' | grep -oE '[0-9A-F-]{36}' | head -1)}"
GATES=build/gates
mkdir -p "$GATES"

# Apple's four quality checks run before every TestFlight upload and follow the app as
# screens come and go (owner rule 2026-10-02, all iOS apps; Haukley 2026-10-07):
#   1. Swift Testing  - the @Test suites in HaukleyTests must run and pass
#   2. XCUITest       - AccessibilityAuditTests: every tab found at run time, the title
#                       sheet, the largest text size; on iPhone AND iPad
#   3. XCTMetric      - PerformanceTests, judged by scripts/perf_gate.py against the
#                       median of the last 5 passing ships (scripts/perf_baseline.json)
#   4. MetricKit      - Services/MetricsReporter.swift still subscribed at launch; the
#                       Xcode Organizer's field numbers printed (report only)
# plus scripts/check_test_coverage.py: every view with ids is reached by a UI test, and no
# UI test queries an identifier the app no longer has.
# Run the whole script under the shared simulator lock when other agents ship too:
#   flock /tmp/claude-ios-ship.lock iphone/scripts/ship.sh

# Regenerate BEFORE testing: a Swift file added since the last generate is in no target,
# and its tests silently never run (Marracat, 2026-10-03).
echo "==> regenerating xcodeproj"
xcodegen generate --quiet

echo "==> MetricKit still wired (metrics + diagnostics)"
grep -q "MXMetricManager.shared.add" Haukley/Services/MetricsReporter.swift \
  && grep -q "\[MXDiagnosticPayload\]" Haukley/Services/MetricsReporter.swift \
  && grep -q "MetricsReporter.shared.start()" Haukley/App/HaukleyApp.swift \
  || { echo "error: MetricsReporter (MetricKit) is no longer subscribed at launch" >&2; exit 1; }

echo "==> every screen is reached by a UI test"
python3 scripts/check_test_coverage.py

echo "==> smoke-testing a cold launch on $SIM_UDID"
./scripts/smoke_test.sh

# xcodebuild prints an "Executed" summary per test class and per bundle, so one green
# class line (e.g. the skipped screenshot class) proves nothing. Pass only if some line
# ran at least one test and NO line reports a failure.
ui_tests_passed() {
    grep -qE "Executed [1-9][0-9]* tests?, with " "$1" &&
        ! grep -E "Executed [0-9]+ tests?, with " "$1" | grep -qE "with ([0-9]+ tests? skipped and )?[1-9][0-9]* failures?"
}

# Swift Testing cases are the ones not named test...() (XCTest's convention).
swift_testing_passed() {
    xcrun xcresulttool get test-results tests --path "$1" | python3 -c '
import json, sys
n = 0
def walk(node):
    global n
    for c in node.get("children", []):
        if c.get("nodeType") == "Test Case" and not c["name"].startswith("test") and c.get("result") == "Passed":
            n += 1
        walk(c)
for t in json.load(sys.stdin)["testNodes"]:
    walk(t)
print(f"==> Swift Testing: {n} test(s) passed")
sys.exit(0 if n else 1)'
}

if [[ "${SHIP_SKIP_TESTS:-0}" != "1" ]]; then
    log=$(mktemp)
    for dev in "iPhone:$SIM_UDID" "iPad:$IPAD_UDID"; do
        name=${dev%%:*}; udid=${dev#*:}
        echo "==> unit + UI tests incl. the accessibility audit on $name ($udid)"
        rm -rf "$GATES/$name.xcresult"
        xcodebuild -project Haukley.xcodeproj -scheme Haukley \
            -destination "platform=iOS Simulator,id=$udid" -derivedDataPath "build/smoke-$name" \
            -resultBundlePath "$GATES/$name.xcresult" -skip-testing:HaukleyUITests/PerformanceTests \
            -retry-tests-on-failure -test-iterations 2 test 2>&1 | tee "$log" | grep -E "Test Case .*(passed|failed)|Executed" || true
        # xcodebuild can "succeed" with zero tests run; ui_tests_passed requires the count.
        if ! ui_tests_passed "$log"; then
            echo "error: $name UI tests failed or none ran" >&2; exit 1
        fi
        grep -q "AccessibilityAuditTests testEveryTab\]' passed" "$log" \
            || { echo "error: the accessibility audit did not pass on $name" >&2; exit 1; }
        swift_testing_passed "$GATES/$name.xcresult" || { echo "error: no Swift Testing tests ran on $name" >&2; exit 1; }
    done

    echo "==> performance (iPhone)"
    rm -rf "$GATES/Perf.xcresult"
    xcodebuild -project Haukley.xcodeproj -scheme Haukley \
        -destination "platform=iOS Simulator,id=$SIM_UDID" -derivedDataPath build/smoke-iPhone \
        -only-testing:HaukleyUITests/PerformanceTests -resultBundlePath "$GATES/Perf.xcresult" test >/dev/null 2>&1 \
        || { echo "error: PerformanceTests failed (see $GATES/Perf.xcresult)" >&2; exit 1; }
    python3 scripts/perf_gate.py "$GATES/Perf.xcresult" --record
fi

echo "==> Xcode Organizer: what real phones reported for recent builds"
"$PY" scripts/organizer_report.py || echo "warning: Organizer report unavailable"

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
