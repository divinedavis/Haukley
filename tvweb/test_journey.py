"""Remote-control journey test for the LG/Samsung TV app, in Chrome at 1920x1080.

Drives tvweb/dist/webos (run build.sh first) with keyboard events only: arrows, Enter, and
Back (Escape stands in for the remote's Back key; the app maps webOS 461 / Tizen 10009 too).
Real Chrome (not Playwright's Chromium) so H.264 video decodes. Web security is off because
the CDN only allows haukley.com as a CORS origin; on the TVs native HLS needs no CORS.

Usage: ~/.venvs/dhcr-map/bin/python tvweb/test_journey.py [--out DIR]
Exit code 0 = every check passed.
"""
import argparse
import functools
import http.server
import pathlib
import sys
import threading
import time

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent
KEYBOARD = ["ABCDEF", "GHIJKL", "MNOPQR", "STUVWX", "YZ1234", "567890"]
failures = []


def check(ok, what):
    print(("PASS " if ok else "FAIL ") + what, flush=True)
    if not ok:
        failures.append(what)


def serve(directory):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    handler.log_message = lambda *a: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "dist" / "journey"))
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    srv = serve(ROOT / "dist" / "webos")
    url = f"http://127.0.0.1:{srv.server_port}/index.html"

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True, args=[
            "--autoplay-policy=no-user-gesture-required", "--disable-web-security", "--mute-audio"])
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        def key(k, n=1, wait=0.35):
            for _ in range(n):
                page.keyboard.press(k)
                time.sleep(wait)

        def focused():
            return page.evaluate("""() => { const f = document.querySelector('.focused');
                if (!f) return null; const r = f.getBoundingClientRect();
                return {key: f.dataset.key, id: f.dataset.id || null, g: f.dataset.g,
                        x: r.left, y: r.top, w: r.width, h: r.height}; }""")

        def layout_ok(step):
            f = focused()
            on = bool(f) and f["x"] >= -2 and f["y"] >= -2 and f["x"] + f["w"] <= 1922 and f["y"] + f["h"] <= 1082
            check(on, f"{step}: focus ring visible on screen ({f and f['key']})")
            ow = page.evaluate("() => [document.documentElement.scrollWidth, document.body.scrollWidth, window.scrollX]")
            check(max(ow[:2]) <= 1920 and ow[2] == 0, f"{step}: no horizontal overflow {ow}")

        def shot(name):
            page.screenshot(path=str(out / f"{name}.png"))

        # Serve the packaged catalog for the live one so the journey tests this build's catalog
        # (it equals the live copy once scripts/deploy_web.sh has run).
        page.route("https://haukley.com/watch/catalog/catalog.json",
                   lambda r: r.fulfill(path=str(ROOT / "dist" / "webos" / "catalog.json"),
                                       headers={"Access-Control-Allow-Origin": "*"}))
        page.goto(url)
        page.wait_for_selector(".card", timeout=20000)
        time.sleep(3)  # hero + first rows' art
        ids_home = set(page.eval_on_selector_all("#screen .scroller:not([hidden]) .card[data-id]", "els => els.map(e => e.dataset.id)"))
        check(len(ids_home) >= 40, f"home shows rows of titles ({len(ids_home)} distinct titles on Home)")
        check(focused()["key"] == "hero:play", "focus starts on the hero Play button")
        layout_ok("home")
        shot("1-home")

        # Live TV: the first row is the live channel (catalog kind "live").
        key("ArrowDown")
        fl = focused()
        check(fl["g"] == "row:live" and fl["id"] == "haukley-weather", f"Down reaches the Live TV row ({fl['key']})")
        key("Enter", wait=2.5)
        meta = page.inner_text(".detail-info .meta")
        play_label = page.inner_text('[data-key="detail:play"]')
        check(meta.startswith("LIVE"), f"live title page says LIVE instead of a runtime ({meta!r})")
        check("Watch Live" in play_label, f"live title page offers Watch Live ({play_label!r})")
        check(page.query_selector('[data-key="detail:restart"]') is None, "no Start Over on a live channel")
        shot("2b-live-detail")
        key("Enter", wait=1)
        check(page.is_visible("#player"), "Watch Live opens the player")
        live_t, t0, lst = None, time.time(), {}
        while time.time() - t0 < 60:
            lst = page.evaluate("""() => { const v = document.getElementById('video'); const p = document.getElementById('player');
                return {t: v.currentTime, paused: v.paused, ad: p.classList.contains('ad'), live: p.classList.contains('live'),
                        err: !document.getElementById('p-error').hidden}; }""")
            if lst["err"]:
                break
            if not lst["paused"] and lst["t"] > 0:
                if live_t is None:
                    live_t = lst["t"]
                elif lst["t"] - live_t >= 2:
                    break
            time.sleep(1)
        check(live_t is not None and lst["t"] - live_t >= 2, f"the live channel plays (currentTime {live_t} -> {lst.get('t')}, error={lst.get('err')})")
        check(lst.get("live") and not lst.get("ad"), "player is in live mode with no ad")
        check(not page.is_visible("#p-bar") and page.is_visible("#p-live"), "LIVE tag replaces the seek bar")
        check(page.evaluate("player.ticket") is None, "no ad ticket requested for live")
        shot("6b-live-player")
        key("Escape", wait=1.5)
        check(not page.is_visible("#player"), "Back closes the live player")
        check(not any(k.startswith("haukley-weather:") for k in page.evaluate(
            "Object.keys(JSON.parse(localStorage.getItem('haukley.progress.v1') || '{}'))")),
            "live playback saves no progress (no Continue Watching entry)")
        key("Escape", wait=1.5)
        check(focused()["id"] == "haukley-weather", "Back returns Home to the Live TV tile")

        key("ArrowDown")
        f1 = focused()
        check(f1["g"].startswith("row:"), f"Down moves focus into the first row ({f1['key']})")
        time.sleep(1)
        shot("2a-top10")
        key("ArrowRight", 5)
        f2 = focused()
        check(f2["g"] == f1["g"] and f2["key"] != f1["key"], f"Right moves along the row ({f2['key']})")
        key("ArrowDown", 2)
        f3 = focused()
        check(f3["g"] != f1["g"], f"Down twice reaches a lower row ({f3['g']})")
        layout_ok("rows")
        time.sleep(1.5)
        shot("2-rows")

        target = f3["id"]
        key("Enter", wait=2.5)
        check(focused()["key"] == "detail:play", f"OK opens the title page for {target}")
        key("ArrowDown", wait=1)
        check(focused()["g"].startswith("row:more-"), "Down reaches More Like This")
        layout_ok("detail more-like-this")
        shot("3a-detail-more")
        key("ArrowUp", wait=1)
        check(focused()["key"] == "detail:play", "Up returns to Play")
        title = page.inner_text(".detail-title")
        layout_ok("detail")
        shot("3-detail")

        key("Enter", wait=1)
        check(page.is_visible("#player"), "Play opens the player")
        # Pre-roll (Google's sample VAST) then the film; wait for the film itself to advance.
        saw_ad, playing, t0 = False, False, time.time()
        while time.time() - t0 < 90:
            st = page.evaluate("""() => { const v = document.getElementById('video'); const p = document.getElementById('player');
                return {ad: p.classList.contains('ad'), t: v.currentTime, paused: v.paused, err: !document.getElementById('p-error').hidden}; }""")
            saw_ad = saw_ad or st["ad"]
            if st["err"]:
                break
            if not st["ad"] and st["t"] > 3 and not st["paused"]:
                playing = True
                break
            time.sleep(1)
        # The live VMAP decides whether a pre-roll exists (breaks may point at an empty VAST).
        print(f"     pre-roll played: {saw_ad}")
        check(playing, f"the film plays after the pre-roll (t={st['t']:.1f}s, error={st['err']})")
        t_before = page.evaluate("document.getElementById('video').currentTime")
        key("ArrowRight", wait=1.5)
        t_after = page.evaluate("document.getElementById('video').currentTime")
        check(t_after - t_before >= 8, f"Right skips ahead 10s ({t_before:.1f} -> {t_after:.1f})")
        time.sleep(1)
        shot("6-player")

        key("Escape", wait=1.5)
        check(not page.is_visible("#player"), "Back closes the player")
        check(focused()["key"] in ("detail:play", "detail:restart"), "…and returns to the title page")
        key("Escape", wait=1.5)
        f4 = focused()
        check(f4["key"] == f3["key"], f"Back returns Home with focus where it was ({f4['key']})")

        # Up to the tab bar, across to Search.
        key("ArrowUp", 6)
        check(focused()["key"].startswith("tab:"), "Up reaches the tab bar")
        key("ArrowRight", 3)
        check(focused()["key"] == "tab:search", "Right reaches the Search tab")
        key("Enter", wait=1.5)
        key("ArrowDown")
        check(focused()["key"].startswith("key:"), f"Down from the Search tab lands on the keyboard ({focused()['key']})")
        word = "GENERAL"
        for ch in word:
            row = next(i for i, r in enumerate(KEYBOARD) if ch in r)
            col = KEYBOARD[row].index(ch)
            cur = focused()["key"].split(":")[1]
            crow = next(i for i, r in enumerate(KEYBOARD) if cur in r)
            ccol = KEYBOARD[crow].index(cur)
            key("ArrowDown" if row > crow else "ArrowUp", abs(row - crow), wait=0.15)
            key("ArrowRight" if col > ccol else "ArrowLeft", abs(col - ccol), wait=0.15)
            key("Enter", wait=0.2)
        q = page.inner_text("#query")
        check(q == word, f"on-screen keyboard types the query ({q!r})")
        res = page.eval_on_selector_all("#results .card", "els => els.map(e => e.dataset.id)")
        check("the-general" in res, f"search finds The General ({res[:5]})")
        layout_ok("search")
        time.sleep(1.5)
        shot("4-search")
        key("ArrowRight", 6)
        check(focused()["g"].startswith("res:"), "Right crosses from the keyboard into the results")
        key("Enter", wait=2)
        check(focused()["key"] == "detail:play", "OK on a result opens its title page")
        key("Escape", wait=1)
        key("Escape", wait=1.5)
        check(page.is_visible(".hero"), "Back from the Search tab goes to Home")

        # Movies tab: every title, grouped by genre.
        key("ArrowUp", 3)
        key("ArrowRight")
        check(focused()["key"] == "tab:movies", "tab bar reaches Movies")
        key("Enter", wait=2)
        ids_movies = set(page.eval_on_selector_all("#screen .scroller:not([hidden]) .card[data-id]", "els => els.map(e => e.dataset.id)"))
        n_movies = page.evaluate("state.titles.filter(t => t.kind === 'movie').length")
        check(len(ids_movies) == n_movies, f"Movies tab lists all {n_movies} films ({len(ids_movies)})")
        kinds = set(page.evaluate(f"{sorted(ids_movies)}.map(id => state.byId.get(id).kind)"))
        check(kinds == {"movie"}, f"Movies tab has no shows ({kinds})")
        key("ArrowDown")
        key("ArrowDown", wait=1.5)
        layout_ok("movies")
        shot("5-movies")
        key("Escape", wait=1.5)

        # Shows tab -> a series -> its episodes -> play episode 2 -> resume on the title page.
        key("ArrowUp", 3)
        key("ArrowRight", 2)
        check(focused()["key"] == "tab:shows", f"tab bar reaches Shows ({focused()['key']})")
        key("Enter", wait=2)
        ids_shows = set(page.eval_on_selector_all("#screen .scroller:not([hidden]) .card[data-id]", "els => els.map(e => e.dataset.id)"))
        n_shows = page.evaluate("state.titles.filter(t => t.kind === 'show').length")
        check(n_shows >= 1 and len(ids_shows) == n_shows, f"Shows tab lists all {n_shows} series ({len(ids_shows)})")
        layout_ok("shows")
        shot("8-shows")
        key("ArrowDown")
        show = focused()["id"]
        key("Enter", wait=2.5)
        check(page.inner_text(".detail .meta, .detail-info .meta").find("Episodes") >= 0, f"show page meta counts episodes ({show})")
        key("ArrowDown", wait=1)
        check(focused()["key"] == "ep:1", f"Down from Play reaches episode 1 ({focused()['key']})")
        n_eps = page.eval_on_selector_all(".card.episode", "els => els.length")
        check(n_eps == page.evaluate(f"state.byId.get('{show}').episodes.length"), f"title page lists every episode ({n_eps})")
        layout_ok("episodes")
        time.sleep(1)
        shot("9-episodes")
        key("ArrowRight", wait=0.6)
        check(focused()["key"] == "ep:2", "Right moves to episode 2")
        key("Enter", wait=1)
        check("E2" in page.inner_text("#p-title"), f"player shows the episode ({page.inner_text('#p-title')!r})")
        want = page.evaluate(f"state.byId.get('{show}').episodes[1].stream")
        t0, playing = time.time(), False
        while time.time() - t0 < 60:
            st = page.evaluate("() => { const v = document.getElementById('video'); return {t: v.currentTime, paused: v.paused, ad: document.getElementById('player').classList.contains('ad')}; }")
            if not st["ad"] and st["t"] > 3 and not st["paused"]:
                playing = True
                break
            time.sleep(1)
        check(playing, "episode 2 plays")
        check(page.evaluate("player.episode") == 2, "player tracks episode 2 (ad events + progress)")
        src = page.evaluate("(player.hls && player.hls.url) || document.getElementById('video').currentSrc")
        check(src == want, f"episode 2's own stream loads ({src[-40:]})")
        check(page.is_visible("#rated"), "rating card shows at the start of the episode")
        # Past the 30 s resume threshold but short of the end, even for a two-minute short.
        page.evaluate("(() => { const v = document.getElementById('video'); v.currentTime = Math.min(60, Math.max(35, v.duration * 0.5)); })()")
        time.sleep(2)
        key("Escape", wait=1.5)
        label = page.inner_text('[data-key="detail:play"]')
        check(label.startswith("Resume E2"), f"title page offers Resume E2 ({label!r})")
        check(page.evaluate(f"!!JSON.parse(localStorage.getItem('haukley.progress.v1'))['{show}:2']"), "progress saved per episode")
        key("Escape", wait=1.5)
        key("Escape", wait=1.5)
        cw = page.eval_on_selector_all('[data-row="continue"] .card', "els => els.map(e => [e.dataset.id, e.dataset.ep])")
        check([show, "2"] in cw, f"Continue Watching has the show at episode 2 ({cw[:3]})")

        # A title with an advisory shows it on its page.
        adv = page.evaluate("(state.titles.find(t => t.advisory) || {}).id")
        page.evaluate(f"push('detail', '{adv}')")
        time.sleep(1.5)
        check(page.is_visible(".advisory") and "Advisory" in page.inner_text(".advisory"), f"advisory shown on the title page ({adv})")
        shot("10-advisory")
        key("Escape", wait=1.5)

        # LG Magic Remote pointer: hover focuses, click opens/plays, wheel scrolls, click toggles pause.
        def center(sel):
            b = page.locator(sel).first.bounding_box()
            return b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
        x, y = page.evaluate("""() => { const c = [...document.querySelectorAll('#screen .scroller:not([hidden]) .rows .card')]
            .map(e => e.getBoundingClientRect()).find(r => r.top > 0 && r.top < 1000 && r.left >= 0 && r.right <= 1920);
            return [c.left + c.width / 2, Math.min(c.top + c.height / 2, (c.top + 1080) / 2)]; }""")
        page.mouse.move(x - 5, y - 5)
        page.mouse.move(x, y)
        time.sleep(0.6)
        hovered = focused()
        check(hovered["g"].startswith("row:"), f"pointer hover focuses a card ({hovered['key']})")

        def wait_playing():
            t0 = time.time()
            while time.time() - t0 < 60:
                st = page.evaluate("() => { const v = document.getElementById('video'); return {t: v.currentTime, paused: v.paused, ad: document.getElementById('player').classList.contains('ad')}; }")
                if not st["ad"] and st["t"] > 2 and not st["paused"]:
                    return True
                time.sleep(1)
            return False

        # A Continue Watching card plays straight away; any other card opens its title page.
        page.mouse.click(x, y)
        time.sleep(2.5)
        if hovered["key"].startswith("continue:"):
            check(page.is_visible("#player") and wait_playing(), "pointer click on Continue Watching resumes playback")
            key("Escape", wait=1.5)
            key("ArrowDown", wait=0.5)
            key("Enter", wait=2.5)
        check(page.is_visible(".detail-title"), "pointer/OK opens a title page")
        page.mouse.move(*center('[data-key="detail:play"]'))
        page.mouse.move(*[v + 3 for v in center('[data-key="detail:play"]')])
        time.sleep(0.4)
        check(focused()["key"] == "detail:play", "pointer hover focuses Play")
        page.mouse.click(*center('[data-key="detail:play"]'))
        check(wait_playing(), "pointer click on Play starts the film")
        page.mouse.click(960, 540)
        time.sleep(0.8)
        check(page.evaluate("document.getElementById('video').paused"), "pointer click on the picture pauses")
        key("Escape", wait=1.5)
        key("Escape", wait=1.5)
        before = focused()["key"]
        page.mouse.move(960, 700)
        page.mouse.wheel(0, 200)
        time.sleep(1)
        check(focused()["key"] != before, f"wheel moves between rows ({before} -> {focused()['key']})")
        key("ArrowUp", 8)

        # Back on Home = exit confirm (store certification requirement).
        key("Escape", wait=1)
        check(page.is_visible("#dialog"), "Back on Home asks to exit")
        check(focused()["key"] == "dialog:0", "exit dialog focuses Cancel")
        shot("7-exit")
        key("Enter", wait=1)
        check(not page.is_visible("#dialog"), "Cancel closes the exit dialog and stays in the app")
        layout_ok("after exit cancel")

        check(not errors, f"no JavaScript errors ({errors[:3]})")
        browser.close()
    srv.shutdown()
    print(f"\n{len(failures)} failed; screenshots in {out}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
