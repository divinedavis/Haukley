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
