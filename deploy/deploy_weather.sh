#!/usr/bin/env bash
# Deploy the Haukley Weather live channel to the droplet (idempotent).
#   code   -> /opt/haukley-live/weather (root-owned, read-only to the service)
#   output -> /var/www/haukley-live/weather, served at https://haukley.com/live/weather/
#   state  -> /var/lib/haukley-live (systemd StateDirectory)
# The /live/ nginx location lives in deploy/nginx-haukley.conf (scp + nginx -t + reload).
set -euo pipefail
cd "$(dirname "$0")/.."
HOST=root@104.236.120.144
python3 tests/run_unit.py >/dev/null
ssh "$HOST" 'set -e
  command -v ffmpeg >/dev/null || DEBIAN_FRONTEND=noninteractive apt-get install -y -q ffmpeg python3-pil >/dev/null
  id haukleylive >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin haukleylive
  mkdir -p /opt/haukley-live /var/www/haukley-live/weather
  chown haukleylive:haukleylive /var/www/haukley-live/weather'
rsync -a --delete --exclude __pycache__ live/weather/ "$HOST":/opt/haukley-live/weather/
scp -q deploy/haukley-weather.service "$HOST":/etc/systemd/system/haukley-weather.service
ssh "$HOST" 'set -e
  chown -R root:root /opt/haukley-live && chmod -R go-w /opt/haukley-live
  systemctl daemon-reload && systemctl enable -q haukley-weather && systemctl restart haukley-weather'
# The first start renders a cycle before publishing (~1-2 min on the droplet).
for i in $(seq 1 60); do
  if curl -fsS https://haukley.com/live/weather/live.m3u8 2>/dev/null | grep -q '\.ts$'; then
    echo "live: https://haukley.com/live/weather/index.m3u8"; exit 0
  fi
  sleep 5
done
echo "live playlist did not appear; check: ssh $HOST journalctl -u haukley-weather -n 50" >&2
exit 1
