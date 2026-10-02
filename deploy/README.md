# haukley.com deploy

- Host: droplet `104.236.120.144` (shared with other client sites), nginx site `haukley`,
  docroot `/var/www/haukley`, logs `/var/log/nginx/haukley-{access,error}.log`.
- TLS: Let's Encrypt via `certbot --nginx` (auto-renews with the droplet's certbot timer).
- DNS: Namecheap BasicDNS — A `@` and A `www` → 104.236.120.144; EmailType FWD kept.
- `nginx-haukley.conf` is a copy of the live config (certbot-managed lines included).
- **Deploy the site (landing, subpages, /watch player, catalogs, /roku, /ads): `scripts/deploy_web.sh`.**
  It runs `tests/run_fast.sh` and `scripts/check_live.py --local --browser`, snapshots the whole
  live docroot to `/var/backups/haukley-web/<UTC ts>` (15 kept, hard-linked), rsyncs `web/`
  (`--delete`; `web/_src` and the server-only `beta/` excluded), chowns root:root, then runs
  `scripts/check_live.py --match-local --browser` against https://haukley.com and rolls back on
  its own if that fails twice. Never scp single files by hand any more.
- Regenerate before deploying when the catalog changed: `.venv/bin/python scripts/make_web.py`
  (catalog + art -> web/watch/catalog/), make_roku_feed.py, make_vmap.py; subpages:
  `python3 web/_src/build.py`. Bump the `?v=` on app.css/app.js in web/watch/index.html when they change.
- Roll back: `scripts/rollback_web.sh` lists snapshots; `scripts/rollback_web.sh <ts>` restores one
  byte-for-byte and re-runs the live checks.
- Health check any time (read-only): `~/.venvs/dhcr-map/bin/python scripts/check_live.py --browser`.
