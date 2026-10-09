# haukley.com deploy

- Host: droplet `104.236.120.144` (shared with other client sites), nginx site `haukley`,
  docroot `/var/www/haukley`, logs `/var/log/nginx/haukley-{access,error}.log`.
- TLS: Let's Encrypt via `certbot --nginx` (auto-renews with the droplet's certbot timer).
- DNS: Namecheap BasicDNS — A `@` and A `www` → 104.236.120.144; EmailType FWD kept.
- `nginx-haukley.conf` is a copy of the live config (certbot-managed lines included).
- **Deploy the site (landing, subpages, /watch player, catalogs, /roku, /ads): `scripts/deploy_web.sh`.**
  It runs `tests/run_fast.sh` and `scripts/check_live.py --local --browser`, snapshots the whole
  live docroot to `/var/backups/haukley-web/<UTC ts>` (15 kept, hard-linked), rsyncs `web/`
  (`--delete`; `web/_src` excluded), chowns root:root, then runs
  `scripts/check_live.py --match-local --browser` against https://haukley.com and rolls back on
  its own if that fails twice. Never scp single files by hand any more.
- Regenerate before deploying when the catalog changed: `.venv/bin/python scripts/make_web.py`
  (catalog + art -> web/watch/catalog/), make_roku_feed.py, make_vmap.py; subpages:
  `python3 web/_src/build.py`. Bump the `?v=` on app.css/app.js in web/watch/index.html when they change.
- Roll back: `scripts/rollback_web.sh` lists snapshots; `scripts/rollback_web.sh <ts>` restores one
  byte-for-byte and re-runs the live checks.
- Health check any time (read-only): `~/.venvs/dhcr-map/bin/python scripts/check_live.py --browser`.

## Live channels (Haukley Weather)

- `deploy/deploy_weather.sh`: installs ffmpeg/Pillow if missing, the `haukleylive` system user,
  code in `/opt/haukley-live/weather` (root-owned), unit `haukley-weather` (`systemctl restart
  haukley-weather`, logs `journalctl -u haukley-weather`), then waits for the live playlist.
- Output `/var/www/haukley-live/weather` → https://haukley.com/live/weather/index.m3u8 (nginx
  `location /live/` in nginx-haukley.conf). State (`timeline.json`, cached NWS grid points) in
  `/var/lib/haukley-live`. Keeps the 3 newest cycles (~20 MB each).
- A render every 15 min costs ~2 CPU-minutes at nice 15. If NOAA is down the previous cycle
  keeps playing (the "Updated" time on screen shows how old it is).
- NCEP hosts (wpc/nhc/spc.noaa.gov, graphical.weather.gov) answer 403 to this droplet's IP;
  use NESDIS (cdn.star.nesdis.noaa.gov), CPC and api.weather.gov, which don't.
