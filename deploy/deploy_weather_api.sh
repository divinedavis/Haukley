#!/usr/bin/env bash
# Deploy the Haukley local weather API (live/weather/api.py) to the droplet (idempotent).
#   code    -> /opt/haukley-live/weather (shared with the weather channel; root-owned)
#   service -> haukley-weather-api on 127.0.0.1:8131, proxied at https://haukley.com/api/weather/
#   geo DB  -> /var/lib/haukley-live/dbip-city-lite.mmdb, refreshed monthly by haukley-geoip.timer
# The nginx location lives in deploy/nginx-haukley.conf (scp + nginx -t + reload).
set -euo pipefail
cd "$(dirname "$0")/.."
HOST=root@104.236.120.144
python3 tests/run_unit.py >/dev/null
ssh "$HOST" 'set -e
  python3 -c "import maxminddb" 2>/dev/null || DEBIAN_FRONTEND=noninteractive apt-get install -y -q python3-maxminddb >/dev/null
  id haukleylive >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin haukleylive
  mkdir -p /opt/haukley-live'
rsync -a --delete --exclude __pycache__ live/weather/ "$HOST":/opt/haukley-live/weather/
scp -q deploy/haukley-weather-api.service deploy/haukley-geoip.service deploy/haukley-geoip.timer \
  "$HOST":/etc/systemd/system/
ssh "$HOST" 'set -e
  chown -R root:root /opt/haukley-live && chmod -R go-w /opt/haukley-live
  systemctl daemon-reload
  [ -s /var/lib/haukley-live/dbip-city-lite.mmdb ] || systemctl start haukley-geoip.service
  systemctl enable -q --now haukley-geoip.timer
  systemctl enable -q haukley-weather-api && systemctl restart haukley-weather-api'
for i in $(seq 1 20); do
  if curl -fsS "https://haukley.com/api/weather/cities" 2>/dev/null | grep -q new-york-ny; then
    echo "weather API live: https://haukley.com/api/weather/local"; exit 0
  fi
  sleep 2
done
echo "weather API not answering; check: ssh $HOST journalctl -u haukley-weather-api -n 50" >&2
exit 1
