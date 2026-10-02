#!/usr/bin/env bash
# Deploy web/ (haukley.com: landing, /filmmakers /privacy /terms /support, the /watch player,
# its catalog, /roku feeds, /ads) to the droplet, and refuse to leave a broken site up.
#
#   scripts/deploy_web.sh                # test -> snapshot -> copy -> live checks -> auto-rollback
#   scripts/deploy_web.sh --skip-tests   # only when you know why (say so in the commit)
#
# 1. tests/run_fast.sh, then scripts/check_live.py --local --browser against web/ served
#    on localhost (content checks + headless Chromium: / and /watch/ render, no JS errors).
# 2. Snapshot the WHOLE live docroot to $BACKUPS/<UTC timestamp> (rsync --link-dest against
#    the previous snapshot, so unchanged files cost no disk; newest $KEEP kept).
# 3. rsync web/ -> docroot (--delete, --delay-updates; web/_src and the server-only beta/
#    are excluded and never deleted), chown root:root.
# 4. scripts/check_live.py --match-local --browser against https://haukley.com (live bytes
#    must equal web/, stream + Supabase + ad endpoints answer). One re-run for network flake;
#    still failing = scripts/rollback_web.sh <snapshot> and exit 1.
# Refuses to ship uncommitted changes under web/ (another session's WIP) unless ALLOW_DIRTY=1.
# Regenerate first if the catalog changed: scripts/make_web.py, make_roku_feed.py, make_vmap.py.
set -euo pipefail
cd "$(dirname "$0")/.."
HOST=root@104.236.120.144
DOC=/var/www/haukley
BACKUPS=/var/backups/haukley-web
KEEP=15
PY=${PY:-$HOME/.venvs/dhcr-map/bin/python}   # needs playwright + chromium for --browser
SKIP=${1:-}

if [ -n "$(git status --porcelain -- web)" ] && [ "${ALLOW_DIRTY:-}" != 1 ]; then
  git status --short -- web
  echo "!! uncommitted changes under web/ - commit them (or ALLOW_DIRTY=1 if they are yours)" >&2
  exit 1
fi

if [ "$SKIP" != "--skip-tests" ]; then
  echo "== fast tests"
  tests/run_fast.sh
  echo "== checks against web/ served locally"
  "$PY" scripts/check_live.py --local --browser
fi

echo "== snapshotting what is live now"
SNAP=$(date -u +%Y%m%dT%H%M%SZ)
ssh "$HOST" "set -e; mkdir -p $BACKUPS; chmod 700 $BACKUPS; prev=\$(ls -1d $BACKUPS/*/ 2>/dev/null | tail -1)
  rsync -a \${prev:+--link-dest=\$prev} $DOC/ $BACKUPS/$SNAP/
  ls -1d $BACKUPS/*/ | head -n -$KEEP | xargs -r rm -rf"
echo "   $BACKUPS/$SNAP (scripts/rollback_web.sh $SNAP)"

echo "== deploying"
rsync -a --delete --delay-updates --exclude _src --exclude beta --exclude .DS_Store web/ "$HOST:$DOC/"
ssh "$HOST" "chown -R root:root $DOC"

echo "== checks against the live site"
if ! "$PY" scripts/check_live.py --match-local --browser; then
  echo "== re-running the live checks once"
  if ! "$PY" scripts/check_live.py --match-local --browser; then
    echo "!! live checks still failing - rolling back to $SNAP" >&2
    scripts/rollback_web.sh "$SNAP" || true
    exit 1
  fi
fi
echo "deployed; snapshot $SNAP"
