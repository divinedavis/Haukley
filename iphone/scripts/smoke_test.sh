#!/usr/bin/env bash
# Build for the simulator, cold-launch, and confirm the app is still alive after 6s
# with no new crash report. Run before every TestFlight ship.
#   SIM_UDID=<free iPhone simulator> iphone/scripts/smoke_test.sh
set -euo pipefail
cd "$(dirname "$0")/.."
: "${SIM_UDID:?set SIM_UDID to a free iPhone simulator}"
xcodebuild -project Haukley.xcodeproj -scheme Haukley -destination "platform=iOS Simulator,id=$SIM_UDID" \
    -derivedDataPath build/smoke -quiet build CODE_SIGNING_ALLOWED=NO
xcrun simctl boot "$SIM_UDID" 2>/dev/null || true
xcrun simctl bootstatus "$SIM_UDID" -b >/dev/null
before=$(ls ~/Library/Logs/DiagnosticReports 2>/dev/null | grep -c '^Haukley' || true)
xcrun simctl install "$SIM_UDID" build/smoke/Build/Products/Debug-iphonesimulator/Haukley.app
xcrun simctl terminate "$SIM_UDID" com.haukley.app 2>/dev/null || true
xcrun simctl launch "$SIM_UDID" com.haukley.app >/dev/null
sleep 6
# Capture first: `cmd | grep -q` under pipefail fails with SIGPIPE when grep exits early.
running=$(xcrun simctl spawn "$SIM_UDID" launchctl list)
if ! grep -q com.haukley.app <<<"$running"; then
    echo "smoke: Haukley is not running 6s after launch" >&2; exit 1
fi
after=$(ls ~/Library/Logs/DiagnosticReports 2>/dev/null | grep -c '^Haukley' || true)
if [[ "$after" -gt "$before" ]]; then
    echo "smoke: new Haukley crash report in ~/Library/Logs/DiagnosticReports" >&2; exit 1
fi
echo "smoke: Haukley launched and stayed up"
