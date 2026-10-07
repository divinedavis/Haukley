#!/usr/bin/env bash
# Put the haukley.com docroot back exactly as a deploy_web.sh snapshot found it.
#
#   scripts/rollback_web.sh                    # list snapshots, newest last
#   scripts/rollback_web.sh 20261001T1830Z     # restore one (whole docroot, --delete)
#
# deploy_web.sh calls this on its own when the live checks fail twice. Snapshots hold the
# whole docroot, so a restore is byte-identical.
set -euo pipefail
cd "$(dirname "$0")/.."
HOST=root@104.236.120.144
DOC=/var/www/haukley
BACKUPS=/var/backups/haukley-web
PY=${PY:-$HOME/.venvs/dhcr-map/bin/python}
SNAP=${1:-}
if [ -z "$SNAP" ]; then
  ssh "$HOST" "ls -1 $BACKUPS"
  exit 0
fi
case "$SNAP" in *[!0-9TZ]*) echo "bad snapshot name: $SNAP" >&2; exit 1;; esac
ssh "$HOST" "set -e; test -d $BACKUPS/$SNAP
  rsync -a --delete --delay-updates $BACKUPS/$SNAP/ $DOC/
  chown -R root:root $DOC"
echo "== restored $SNAP; checking the live site"
"$PY" scripts/check_live.py
echo "rolled back to $SNAP"
