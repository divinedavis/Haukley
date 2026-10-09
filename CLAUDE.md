# Haukley (repo: StreamTV)

Product overview, platforms and run commands: README.md. Site deploy: deploy/README.md.

## Tests

**Every change adds, updates AND deletes tests in the same commit**, and the commit body says
which ("Tests added: … / updated: … / deleted: …", "none" is a valid answer for each). A test
for removed behaviour is deleted, not skipped; a test that never ran is fixed or deleted.

- `tests/run_fast.sh` (or `npm run test:fast`, ~7 s): every fast automated test
  - `tsc --noEmit` (React Native TV app)
  - Jest, `__tests__/` (RN catalog, history, App)
  - `python3 tests/run_unit.py`: every `tests/test_*.py` (unittest classes AND bare
    `def test_*` functions). `test_catalog.py` checks the source catalog and the web / iPhone /
    Roku copies (stale regeneration, rows, rights lines, CDN streams, art);
    `test_web_pages.py` checks the haukley.com pages (viewport, `web/_src` build not stale).
  - Roku: `roku/tests/*_test.brs` in brs-node (`npx -p brs-node brs-cli`, not `npx brs-cli`).
    brs-cli always exits 0; run_fast.sh fails on any `FAIL` line.
- Live-DB tests: `python3 tests/db/run_db_tests.py` runs `tests/db/test_*.sql` against the
  Supabase project (each file is one DO block that raises `ALL_PASS`, so it rolls back). Run
  after every migration touching what they cover; not in run_fast (network).
- iPhone unit tests (Swift Testing): `iphone/HaukleyTests`, run by the scheme's test action.
- **pre-push hook** (`.githooks/pre-push`, enable once per checkout with
  `scripts/install_hooks.sh`): gitleaks over exactly the pushed commits + `tests/run_fast.sh`.
  It is the CI: there are deliberately **no GitHub Actions** (private repo, nothing that can
  bill). `git push --no-verify` only in an emergency, with the reason in the next commit.
- **Web deploy**: `scripts/deploy_web.sh` runs the fast tests and `scripts/check_live.py
  --local --browser`, snapshots the live docroot, copies, runs `check_live.py --match-local
  --browser` on https://haukley.com and auto-rolls back on failure (`scripts/rollback_web.sh`).
- Slow suites (not in the hook; run per platform after every change, see the journey-suite rule):
  - LG/Samsung TV web app: `tvweb/release.sh` (journey + LG self-check)
  - Android TV / Fire TV: `scripts/tv_journey.py --serial …`
  - iPhone: XCUITests in `iphone/HaukleyUITests` via `iphone/scripts/ship.sh` / `smoke_test.sh`
  - tvOS: simulator build (README); Roku UI: brs-node emulator on `roku/dist` zip

## App Store

`iphone/scripts/ship.sh` and `ios/scripts/ship_tvos.sh` are TestFlight-only.
`iphone/scripts/submit_for_review.py --platform IOS|TV_OS` is a dry run unless `--submit`;
with it, every update gets a 7-day phased release (INACTIVE until Apple releases it).
Submit only on the owner's explicit go.

## Auth (Supabase, web /watch only)

- Sign-up is autoconfirmed and there is **no email verification** (owner rule) - so never let
  a second sign-in method attach itself to an existing account by email match. Migration
  0015's trigger on `auth.identities` refuses any non-email identity for a user who already
  has an email/password identity (GoTrue's automatic linking can't be switched off on hosted
  Supabase). Keep `security_manual_linking_enabled` OFF. Before enabling Google: create a
  Haukley-only OAuth client, run `tests/db/run_db_tests.py`, and test that a password
  account's address gets the "already has a Haukley password" message on /watch.
- Password changes need a fresh session (`security_update_password_require_reauthentication`):
  the reset-link session is fresh, so recovery still works without a nonce email.
- Captcha: not set up (needs an hCaptcha/Turnstile account from the owner).

## Video delivery (DO Spaces CDN `haukley-media`, audit 2026-10-07 L3)

- Streams are public, unsigned HLS on `haukley-media.nyc3.cdn.digitaloceanspaces.com`; bucket
  CORS allows only `https://haukley.com`, so other websites can't play them in a browser, but
  anyone can download them directly. There is **no geo limit**, although the public-domain
  rights are US-only (the apps are US-only in every store).
- Why not fixed: Spaces CDN serves only public objects (pre-signed URLs work on the origin
  endpoint, not the CDN) and has no geo rules. Signing would mean a proxy that rewrites every
  playlist and presigns each segment, on every platform (Roku/LG/Samsung/iPhone/TV apps
  cache the catalog's stream URLs), and would lose CDN caching. Revisit before licensed
  (non-PD) content: put the bucket behind Cloudflare (or a droplet nginx with GeoIP2 +
  `secure_link`) and ship clients that ask the API for a short-lived playback URL.
- Don't widen the bucket CORS (`*`): the TV apps don't need it (native players send no Origin).

## Live channels (kind "live")

- Catalog `live` list (scripts/catalog.json) → kind `"live"` titles in every platform copy and the
  "Live TV" row (rows.json). Every app: LIVE tag instead of runtime, "Watch Live", no resume
  point, **no watch progress / Continue Watching, no ads** (no VMAP, no start_playback ticket),
  no scrubber. Streams are served from the droplet (`/live/`), not the CDN; tests/test_catalog.py
  allows that host only for live ids.
- Haukley Weather is generated by live/weather/channel.py (NOAA data, U.S. public domain);
  ops in deploy/README.md. Carriage requests for third-party channels: docs/content/outreach-emails.md.

## Email (audit L2)

- No custom SMTP: haukley.com mail is Namecheap forwarding only (no mailbox to send from), so
  Supabase's default sender only reaches project team members - **password-reset emails don't
  reach real viewers**. Owner action: a sending mailbox/provider for haukley.com (e.g. Resend,
  Zoho, Namecheap Private Email) + SPF/DKIM DNS, then set smtp_* via the Management API
  (`PATCH /v1/projects/axgxpwgbpgcqjxoqwtnv/config/auth`, port 465).

## /watch/ CSP (audit L4, 2026-10-07)

- `deploy/nginx-haukley.conf` location /watch/: no `'unsafe-inline'` scripts, connect-src pinned
  to Supabase, the stream CDN and Google ad hosts. `tests/test_web_pages.py` enforces it;
  `check_live.py` checks the live header equals the repo file (nginx is deployed by scp +
  `nginx -t` + reload, not by deploy_web.sh). Keep /watch/index.html free of inline scripts.
- Trade-off: IMA injects a same-origin `about:srcdoc` frame with an inline Open Measurement
  (Active View) bootstrap; it is blocked (hash changes per load; `omidAccessModeRules` LIMITED
  didn't move it). Ads + film still play (26/26 Playwright runs with Google's sample pre-roll).
  **When real GAM ads go live, check viewability in Ad Manager**; if Active View shows no
  data, that frame is why. New ad server hosts in VAST wrappers may also need connect-src
  entries (look for CSP violations in the console).

## npm audit (audit L6, 2026-10-07)

- `shell-quote` is pinned `^1.11.0` via package.json `overrides` (critical command-injection,
  pulled in by react-devtools-core / launch-editor). Remaining advisories are build/test tooling
  only, never shipped in an app bundle: `braces` <=3.0.3 and `sprintf-js` <=1.1.3 have **no
  patched release**; the rest resolve only through jest 30 / RN CLI majors that
  react-native-tvos 0.83 doesn't support. Re-check when react-native-tvos moves up.
