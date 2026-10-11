#!/bin/bash
# Install roku/dist/Haukley-roku.zip on the owner's Roku (developer mode) and have the device
# sign it into the .pkg the Roku dashboard takes (App package). Signing only happens on a
# real Roku that holds the app's genkey key (made on the Streaming Stick 2026-10-10).
#
#   scripts/roku_package.sh [roku-ip]     (default: $ROKU_IP or 192.168.1.245)
#
# Keychain: roku-dev-password (dev web UI, user rokudev), roku-genkey-password.
# Output: ~/Downloads/Haukley-roku-<version>.pkg
set -euo pipefail
cd "$(dirname "$0")/.."
IP="${1:-${ROKU_IP:-192.168.1.245}}"
ZIP=roku/dist/Haukley-roku.zip
DEV_PW=$(security find-generic-password -s roku-dev-password -w)
KEY_PW=$(security find-generic-password -s roku-genkey-password -w)
VER=$(unzip -p "$ZIP" manifest | awk -F= '/^major_version/{a=$2}/^minor_version/{b=$2}/^build_version/{c=$2}END{print a"."b"."c}')
AUTH=(--digest -u "rokudev:$DEV_PW" -sS -m 120)

curl -s -m 5 "http://$IP:8060/query/device-info" | grep -q '<developer-enabled>true' \
  || { echo "Roku at $IP is off, unreachable or not in developer mode"; exit 1; }

out=$(curl "${AUTH[@]}" -F mysubmit=Install -F "archive=@$ZIP" "http://$IP/plugin_install")
grep -qE "Install Success|Identical to previous version" <<<"$out" \
  || { echo "install failed:"; sed 's/<[^>]*>//g' <<<"$out" | grep -iE "fail|error" | head; exit 1; }
echo "installed $VER"

out=$(curl "${AUTH[@]}" -F mysubmit=Package -F "app_name=Haukley/$VER" -F "passwd=$KEY_PW" \
  -F "pkg_time=$(date +%s)000" "http://$IP/plugin_package")
pkg=$(grep -oE 'pkgs//?[^"]+\.pkg' <<<"$out" | head -1) \
  || { echo "package failed:"; sed 's/<[^>]*>//g' <<<"$out" | grep -iE "fail|error|password" | head; exit 1; }
dest="$HOME/Downloads/Haukley-roku-$VER.pkg"
curl "${AUTH[@]}" -o "$dest" "http://$IP/${pkg#/}"
echo "signed package: $dest ($(du -h "$dest" | cut -f1))"
