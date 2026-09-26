#!/bin/bash
# Build a release APK and install + launch it on the Fire TV over Wi-Fi ADB.
# Usage: scripts/firetv.sh [device-ip]   (default: $FIRETV_IP or 192.168.1.155)
set -euo pipefail
cd "$(dirname "$0")/.."
IP="${1:-${FIRETV_IP:-192.168.1.155}}"
export JAVA_HOME="${JAVA_HOME:-/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home}"
export ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"

(cd android && ./gradlew assembleRelease -PreactNativeArchitectures=armeabi-v7a,arm64-v8a -q)
adb connect "$IP:5555" >/dev/null
APK=android/app/build/outputs/apk/release/app-release.apk
# Builds before 2026-09-26 were signed with the debug key; the first install signed with the
# release key needs an uninstall (this clears local Continue Watching on that device).
if ! out=$(adb -s "$IP:5555" install -r "$APK" 2>&1); then
  echo "$out"
  if grep -q INSTALL_FAILED_UPDATE_INCOMPATIBLE <<<"$out"; then
    adb -s "$IP:5555" uninstall com.haukley.tv
    adb -s "$IP:5555" install "$APK"
  else
    exit 1
  fi
fi
adb -s "$IP:5555" shell input keyevent KEYCODE_WAKEUP
adb -s "$IP:5555" shell am force-stop com.haukley.tv
adb -s "$IP:5555" shell am start -n com.haukley.tv/com.streamtv.MainActivity
