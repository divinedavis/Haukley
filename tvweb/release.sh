#!/bin/bash
# Build the LG/Samsung packages and hand them over ONLY if every test passes:
#   1. build.sh                 -> tvweb/dist/*.ipk, *.wgt
#   2. test_journey.py          -> remote-control journey (screenshots feed the store images)
#   3. test_lg_selfcheck.py     -> LG Seller Lounge self-check list, item by item
#   4. make_assets.py --shots + make_ux_scenario.py  -> store screenshots + UX Scenario PDF
#   5. copy to ~/Downloads/Haukley-LG and ~/Downloads/Haukley-Samsung
# Items marked DEVICE in the self-check output still need a real TV / the webOS Cloud Test Lab.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=~/.venvs/dhcr-map/bin/python
tvweb/build.sh
$PY tvweb/test_journey.py > /tmp/haukley-journey.log 2>&1 || { tail -30 /tmp/haukley-journey.log; echo "journey test FAILED"; exit 1; }
tail -1 /tmp/haukley-journey.log
$PY tvweb/test_lg_selfcheck.py > /tmp/haukley-selfcheck.log 2>&1 || { grep -E "FAIL|failed" /tmp/haukley-selfcheck.log; echo "LG self-check FAILED"; exit 1; }
sed -n '/LG self-check answers:/,$p' /tmp/haukley-selfcheck.log
.venv/bin/python tvweb/make_assets.py --shots tvweb/dist/journey > /dev/null
$PY tvweb/make_ux_scenario.py
mkdir -p ~/Downloads/Haukley-LG ~/Downloads/Haukley-Samsung
rm -rf ~/Downloads/Haukley-LG/720 && mkdir -p ~/Downloads/Haukley-LG/720
cp tvweb/dist/*.ipk marketing/lg/* ~/Downloads/Haukley-LG/
cp tvweb/dist/720/*.ipk ~/Downloads/Haukley-LG/720/
cp tvweb/dist/*-unsigned.wgt marketing/samsung/* ~/Downloads/Haukley-Samsung/
echo "released to ~/Downloads/Haukley-LG and ~/Downloads/Haukley-Samsung"
