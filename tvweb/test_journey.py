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

        page.goto(url)
        page.wait_for_selector(".card", timeout=20000)
        time.sleep(3)  # hero + first rows' art
        ids_home = set(page.eval_on_selector_all("#screen .scroller:not([hidden]) .card[data-id]", "els => els.map(e => e.dataset.id)"))
        check(len(ids_home) >= 40, f"home shows rows of titles ({len(ids_home)} distinct titles on Home)")
        check(focused()["key"] == "hero:play", "focus starts on the hero Play button")
        layout_ok("home")
        shot("1-home")

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
        key("ArrowRight", 2)
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
        check(len(ids_movies) == 64, f"Movies tab lists all 64 titles ({len(ids_movies)})")
        key("ArrowDown")
        key("ArrowDown", wait=1.5)
        layout_ok("movies")
        shot("5-movies")
        key("Escape", wait=1.5)

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
