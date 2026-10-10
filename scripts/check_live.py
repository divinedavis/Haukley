"""Health check for haukley.com: real content, not just status codes.

    python3 scripts/check_live.py                    # check https://haukley.com
    python3 scripts/check_live.py --match-local      # ...and require live files == web/ (post-deploy)
    python3 scripts/check_live.py --local            # serve web/ on localhost and check that (pre-deploy)
    ... --browser                                     # also load / and /watch/ in headless Chromium
                                                      #   (needs a python with playwright, e.g.
                                                      #   ~/.venvs/dhcr-map/bin/python)

Read-only: GETs only, no sign-in, nothing written anywhere. Checks every page, the web
player bundle, the catalog every app fetches (web, Roku), ad endpoints (ads.txt, VMAP,
the no-fill VAST), the Roku search feed, security headers, one real HLS stream on the CDN
(master + variant playlist), and the Supabase auth settings endpoint the player calls.
Exit 0 = all passed. Used by scripts/deploy_web.sh and scripts/rollback_web.sh.
"""
import argparse
import functools
import hashlib
import http.server
import json
import pathlib
import re
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
SUPABASE = "https://axgxpwgbpgcqjxoqwtnv.supabase.co"
# Files whose live bytes must equal web/ after a deploy (--match-local).
MATCH = ["index.html", "site.css", "site.js", "ads.txt", "app-ads.txt",
         "filmmakers/index.html", "privacy/index.html", "terms/index.html", "support/index.html",
         "watch/index.html", "watch/app.js", "watch/app.css", "watch/catalog/catalog.json",
         "watch/catalog/ads.json", "roku/catalog.json", "roku/search-feed.json", "ads/no-ad.xml"]
failures = []


def check(ok, what):
    print(("  ok    " if ok else "  FAIL  ") + what, flush=True)
    if not ok:
        failures.append(what)
    return ok


def get(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": "haukley-check-live/1", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()
    except Exception as e:  # DNS, TLS, timeout
        return 0, {}, str(e).encode()


def page(base, path, must, live):
    status, headers, body = get(base + path)
    text = body.decode("utf-8", "replace")
    if not check(status == 200, f"{path} -> {status}"):
        return text
    for m in must:
        check(m in text, f"{path} contains {m!r}")
    if live:
        check("Content-Security-Policy" in headers or "content-security-policy" in {k.lower() for k in headers},
              f"{path} sends a Content-Security-Policy")
    return text


def json_at(base, path):
    status, _, body = get(base + path)
    if not check(status == 200, f"{path} -> {status}"):
        return None
    try:
        return json.loads(body)
    except ValueError:
        check(False, f"{path} is valid JSON")
        return None


def run_http(base, live, match_local):
    print(f"== {base}")
    page(base, "/", ["<title>Haukley", 'name="viewport"', "/watch"], live)
    for p, m in [("/filmmakers/", "Filmmakers"), ("/privacy/", "Privacy Policy"),
                 ("/terms/", "Terms of Use"), ("/support/", "Support")]:
        page(base, p, [m, 'name="viewport"'], live)
    watch = page(base, "/watch/", ['id="app"', 'id="player"'], live)
    if live:
        # The live /watch/ CSP must be the one in deploy/nginx-haukley.conf (strict script/connect).
        conf = (ROOT / "deploy" / "nginx-haukley.conf").read_text()
        want = re.search(r'Content-Security-Policy "([^"]+)"', conf[conf.index("location /watch/ {"):]).group(1)
        _, headers, _ = get(base + "/watch/")
        got = {k.lower(): v for k, v in headers.items()}.get("content-security-policy", "")
        check(got == want, "/watch/ CSP header matches deploy/nginx-haukley.conf")
        # The old sideload zip (audit L7) must stay gone.
        status, _, _ = get(base + "/beta/gI6hDsWGGN/Haukley-roku.zip")
        check(status == 404, f"old /beta/ Roku zip is gone ({status})")
    js = re.search(r'src="(app\.js\?v=[^"]+)"', watch)
    css = re.search(r'href="(app\.css\?v=[^"]+)"', watch)
    if check(bool(js and css), "/watch/ references versioned app.js and app.css"):
        status, _, body = get(f"{base}/watch/{js.group(1)}")
        check(status == 200 and b"SUPABASE_URL" in body and len(body) > 20000, f"/watch/{js.group(1)} is the player bundle")
        status, _, body = get(f"{base}/watch/{css.group(1)}")
        check(status == 200 and len(body) > 2000, f"/watch/{css.group(1)} -> {status}")

    cat = json_at(base, "/watch/catalog/catalog.json")
    first = None
    if cat:
        titles = {t["id"]: t for t in cat.get("titles", [])}
        check(len(titles) >= 50, f"web catalog has {len(titles)} titles")
        check(all(i in titles for i in cat.get("featured", [])), "web catalog featured ids resolve")
        first = titles.get((cat.get("featured") or [None])[0])
        if first:
            status, headers, body = get(f"{base}/watch/catalog/{first['id']}/poster.jpg")
            check(status == 200 and body[:2] == b"\xff\xd8", f"poster art for {first['id']} is a JPEG")
        # Live channels (kind "live", live/ + deploy/deploy_weather.sh): a sliding-window
        # playlist that is still moving, readable cross-origin (LG/Samsung apps run from file://).
        for lt in [t for t in titles.values() if t.get("kind") == "live"]:
            status, headers, body = get(lt["stream"])
            check(status == 200 and b"#EXT-X-STREAM-INF" in body, f"live {lt['id']}: master playlist -> {status}")
            check((headers.get("Access-Control-Allow-Origin") or "") == "*", f"live {lt['id']}: CORS *")
            variant = urllib.parse.urljoin(lt["stream"], body.decode().strip().splitlines()[-1]) if status == 200 else None
            if variant:
                status, _, body = get(variant)
                text = body.decode(errors="replace")
                seq = re.search(r"#EXT-X-MEDIA-SEQUENCE:(\d+)", text)
                check(status == 200 and "#EXTINF" in text and "#EXT-X-ENDLIST" not in text and seq,
                      f"live {lt['id']}: live media playlist (no ENDLIST)")
                seg = [l for l in text.splitlines() if l.endswith(".ts")]
                if seg:
                    status, _, body = get(urllib.parse.urljoin(variant, seg[-1]))
                    check(status == 200 and body[:1] == b"\x47", f"live {lt['id']}: newest segment is MPEG-TS")
    check_weather_api()
    roku = json_at(base, "/roku/catalog.json")
    if roku:
        check(len(roku.get("titles", {})) >= 50 and roku.get("rows"), f"roku catalog has {len(roku.get('titles', {}))} titles + rows")
    feed = json_at(base, "/roku/search-feed.json")
    if feed is not None:
        check(bool(feed), "roku search feed is not empty")

    status, _, body = get(base + "/ads.txt")
    check(status == 200 and b"pub-8077227518694725" in body, "/ads.txt has the AdSense seller line")
    status, _, body = get(base + "/app-ads.txt")
    check(status == 200 and b"DIRECT" in body, "/app-ads.txt -> 200 with a seller line")
    status, _, body = get(base + "/ads/no-ad.xml")
    check(status == 200 and b"<VAST" in body, "/ads/no-ad.xml is a VAST document")
    if first:
        status, _, body = get(f"{base}/ads/vmap/{first['id']}.xml")
        check(status == 200 and b"vmap" in body.lower(), f"/ads/vmap/{first['id']}.xml is a VMAP")

    if first and first.get("stream"):
        status, _, body = get(first["stream"])
        ok = check(status == 200 and body.startswith(b"#EXTM3U"), f"stream master playlist ({first['id']}) -> {status}")
        variant = next((l for l in body.decode("utf-8", "replace").splitlines() if l and not l.startswith("#")), None)
        if ok and check(bool(variant), "master playlist lists a variant"):
            url = urllib.parse.urljoin(first["stream"], variant)
            status, _, body = get(url)
            check(status == 200 and body.startswith(b"#EXTM3U"), f"variant playlist -> {status}")

    if live:
        key = re.search(r'sb_publishable_[A-Za-z0-9_-]+', (WEB / "watch" / "app.js").read_text())
        status, _, body = get(f"{SUPABASE}/auth/v1/settings", {"apikey": key.group(0)} if key else {})
        check(status == 200 and b"external" in body, f"Supabase auth settings (sign-in providers) -> {status}")

    if match_local:
        for rel in MATCH:
            status, _, body = get(f"{base}/{rel}")
            local = (WEB / rel).read_bytes()
            check(status == 200 and hashlib.md5(body).digest() == hashlib.md5(local).digest(),
                  f"live /{rel} matches web/{rel}")


def check_ad_ticket(pg):
    """The /watch player asks start_playback for a signed ticket and sends it (plus a per-event
    seq) with every ad event. Supabase is stubbed here, so nothing is written to the live DB."""
    import json as _json
    sent = []

    def stub(route):
        req = route.request
        sent.append((req.url.rsplit("/", 1)[-1], _json.loads(req.post_data or "null")))
        if req.url.endswith("/rpc/start_playback"):
            route.fulfill(status=200, content_type="application/json",
                          body=_json.dumps({"session_id": "00000000-0000-4000-8000-000000000001",
                                            "token": "1790000000." + "a" * 64}))
        else:
            route.fulfill(status=204, body="")

    pg.route("**/rest/v1/rpc/*", stub)
    try:
        pg.wait_for_function("() => typeof requestTicket === 'function'", timeout=10000)
        pg.evaluate("""async () => {
            if (!state.ads) state.ads = await fetch(ART + 'ads.json').then(r => r.json());  // loads after sign-in
            Object.assign(player, { id: 'probe', episode: 0, sessionId: crypto.randomUUID(),
                                    ticket: requestTicket('probe', 0), seq: 0 });
            logAdEvent('ad_started'); logAdEvent('ad_completed');
            await player.ticket; await new Promise(r => setTimeout(r, 500)); }""")
    except Exception as e:
        check(False, f"/watch/ ad ticket flow ran: {str(e).splitlines()[0]}")
        return
    finally:
        pg.unroute("**/rest/v1/rpc/*")
    starts = [b for u, b in sent if u == "start_playback"]
    events = [b for u, b in sent if u == "log_ad_events"]
    check(starts == [{"title_id": "probe", "episode": 0, "platform": "web"}],
          f"/watch/ requests a playback ticket ({starts})")
    check([(e.get("event"), e.get("seq"), bool(e.get("token")), e.get("session_id")) for e in events]
          == [("ad_started", 1, True, "00000000-0000-4000-8000-000000000001"),
              ("ad_completed", 2, True, "00000000-0000-4000-8000-000000000001")],
          f"/watch/ ad events carry the ticket and a seq ({events})")


def check_weather_api(api="https://haukley.com/api/weather"):
    """Local weather API (live/weather/api.py): always the live host, it isn't part of web/."""
    status, headers, body = get(f"{api}/cities")
    try:
        cities = json.loads(body).get("cities", []) if status == 200 else []
    except ValueError:
        cities = []
    check(len(cities) >= 100 and any(c.get("slug") == "new-york-ny" for c in cities),
          f"weather API /cities -> {status}, {len(cities)} cities")
    status, headers, body = get(f"{api}/local?zip=11201")
    try:
        b = json.loads(body) if status == 200 else {}
    except ValueError:
        b = {}
    check(status == 200 and set(b) >= {"place", "now", "periods", "alerts", "updated", "attribution"}
          and isinstance((b.get("now") or {}).get("temp"), (int, float)),
          f"weather API /local?zip=11201 -> {status} with the contract fields")
    check((headers.get("Access-Control-Allow-Origin") or "") == "*" and "Set-Cookie" not in headers,
          "weather API: CORS * and no cookie")
    status, _, body = get(f"{api}/local?lat=51.5&lon=-0.12")
    check(status == 422 and b"unknown_location" in body, f"weather API outside the US -> {status} unknown_location")


def check_live_channel(pg):
    """A live channel plays in the /watch player as LIVE (no scrubber), with no ad ticket and
    no watch_progress writes. Supabase is stubbed; the stream itself is the real one."""
    sent = []

    def stub(route):
        sent.append(route.request.url.split("/rest/v1/", 1)[-1].split("?")[0])
        route.fulfill(status=204, body="")

    pg.route("**/rest/v1/**", stub)
    try:
        lid = pg.evaluate("""async () => {
            if (!state.catalog) state.catalog = await fetch(ART + 'catalog.json').then(r => r.json());
            state.byId = new Map(state.catalog.titles.map(t => [t.id, t]));
            const t = state.catalog.titles.find(t => t.kind === 'live');
            if (!t) return null;
            state.user = { id: 'probe' }; state.profile = { id: 'probe', name: 'Probe' };
            video.muted = true;
            startPlayback(t.id, 0);
            return t.id; }""")
        if not check(bool(lid), "/watch/ catalog has a live channel"):
            return
        pg.wait_for_function("() => video.currentTime > 2", timeout=45000)
        got = pg.evaluate("""() => { saveProgress(player.id, 0, video.currentTime, 600);
            return { live: player.el.classList.contains('live'), label: $('#p-remaining').textContent,
                     seekDisabled: $('#p-seek').disabled }; }""")
        pg.wait_for_timeout(500)
        check(got == {"live": True, "label": "LIVE", "seekDisabled": True}, f"/watch/ {lid} plays as LIVE ({got})")
        check(not any(u.startswith(("rpc/start_playback", "watch_progress")) for u in sent),
              f"/watch/ {lid}: no ad ticket or progress writes ({sent})")
        pg.evaluate("() => stopPlayback(false)")
    except Exception as e:
        check(False, f"/watch/ live channel plays: {str(e).splitlines()[0]}")
    finally:
        pg.unroute("**/rest/v1/**")


def check_waitlist_form(pg):
    """The landing page's "Get notified" form posts to the rate-limited join_waitlist RPC
    (never the table). Supabase is stubbed, so nothing is written."""
    import json as _json
    sent = []

    def stub(route):
        sent.append((route.request.url.rsplit("/", 1)[-1], _json.loads(route.request.post_data or "null")))
        route.fulfill(status=204, body="")

    pg.route("**/rest/v1/**", stub)
    try:
        form = pg.locator("#notify-hero")
        form.locator("input[type=email]").fill("probe@example.com")
        form.locator("button").click()
        pg.wait_for_selector("#notify-hero .note.ok", timeout=10000)
        check(sent == [("join_waitlist", {"email": "probe@example.com", "source": "web"})],
              f"/ waitlist form posts to rpc/join_waitlist ({sent})")
    except Exception as e:
        check(False, f"/ waitlist form: {str(e).splitlines()[0]}")
    finally:
        pg.unroute("**/rest/v1/**")


def run_browser(base):
    from playwright.sync_api import sync_playwright
    print(f"== browser {base}")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for path, wait_for in [("/", "text=Haukley"), ("/watch/", "text=Sign in to watch")]:
            ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True)
            pg = ctx.new_page()
            errors = []
            pg.on("pageerror", lambda e, errors=errors: errors.append(str(e)))
            try:
                pg.goto(base + path, wait_until="domcontentloaded", timeout=30000)
                pg.wait_for_selector(wait_for, timeout=20000)
                check(True, f"{path} renders ({wait_for})")
            except Exception as e:
                check(False, f"{path} renders ({wait_for}): {str(e).splitlines()[0]}")
            check(not errors, f"{path} has no uncaught JS errors {errors[:2] if errors else ''}")
            if path == "/watch/":
                check_ad_ticket(pg)
                check_live_channel(pg)
            if path == "/":
                check_waitlist_form(pg)
            ctx.close()
        # A Google sign-in the DB refused (0015: Google onto a password account) explains itself.
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True)
        pg = ctx.new_page()
        try:
            pg.goto(base + "/watch/#error=server_error&error_code=unexpected_failure"
                    "&error_description=Database+error+saving+new+user", wait_until="domcontentloaded", timeout=30000)
            pg.wait_for_selector("text=already has a Haukley password", timeout=20000)
            check("#error" not in pg.url, "/watch/ refused Google link: explains + cleans the URL")
        except Exception as e:
            check(False, f"/watch/ refused Google link message: {str(e).splitlines()[0]}")
        ctx.close()
        browser.close()


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve_web(directory):
    handler = functools.partial(QuietHandler, directory=str(directory))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://haukley.com")
    ap.add_argument("--local", action="store_true", help="serve web/ locally and check that instead")
    ap.add_argument("--web", default=str(WEB), help="directory --local serves (default web/)")
    ap.add_argument("--match-local", action="store_true", help="require live files to equal web/")
    ap.add_argument("--browser", action="store_true", help="also load pages in headless Chromium")
    a = ap.parse_args()
    base = serve_web(a.web) if a.local else a.base.rstrip("/")
    run_http(base, live=not a.local, match_local=a.match_local and not a.local)
    if a.browser:
        run_browser(base)
    print(f"{'FAILED: ' + str(len(failures)) + ' check(s)' if failures else 'all checks passed'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
