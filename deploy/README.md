# haukley.com deploy

- Host: droplet `104.236.120.144` (shared with other client sites), nginx site `haukley`,
  docroot `/var/www/haukley`, logs `/var/log/nginx/haukley-{access,error}.log`.
- TLS: Let's Encrypt via `certbot --nginx` (auto-renews with the droplet's certbot timer).
- DNS: Namecheap BasicDNS — A `@` and A `www` → 104.236.120.144; EmailType FWD kept.
- Deploy the landing page:
  ```bash
  scp web/index.html web/favicon.png web/og.jpg root@104.236.120.144:/var/www/haukley/
  scp web/img/*.jpg root@104.236.120.144:/var/www/haukley/img/
  ```
- `nginx-haukley.conf` is a copy of the live config (certbot-managed lines included).
- Deploy the web player (haukley.com/watch/, sign-in required; nginx has its own CSP for it):
  ```bash
  .venv/bin/python scripts/make_web.py            # catalog + art -> web/watch/catalog/
  rsync -a --delete web/watch/ root@104.236.120.144:/var/www/haukley/watch/
  ssh root@104.236.120.144 'chown -R root:root /var/www/haukley'
  ```
  Bump the `?v=` on app.css/app.js in web/watch/index.html when they change.
