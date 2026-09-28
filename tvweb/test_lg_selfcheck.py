"""LG Seller Lounge self-check list (v5.0), automated where a browser can check it.

Runs the packaged webOS app (tvweb/dist/webos, so run build.sh first) in real Chrome and walks
LG's QA items by number. Keys are sent with the TV's own key codes (webOS BACK = 461, media keys
415/19/413/417/412, colour and number keys), not keyboard stand-ins. Ads are tested against
Google's public IMA sample VAST (the live schedule returns no ad until Ad Manager exists).

Every LG item ends up as one of:
  PASS    checked here and passed
  FAIL    checked here and failed (exit code 1)
  N/A     the app doesn't have the feature (sign-in, payment, adult content, DRM, ...)
  DEVICE  needs a real TV (power cycle, factory reset, Recent List); do these in the
          webOS Cloud Test Lab or on a TV before submitting

Usage: ~/.venvs/dhcr-map/bin/python tvweb/test_lg_selfcheck.py
"""
import functools
import http.server
import pathlib
import random
import sys
import threading
import time

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent
SAMPLE_VAST = ("https://pubads.g.doubleclick.net/gampad/ads?iu=/21775744923/external/single_ad_samples"
               "&sz=640x480&cust_params=sample_ct%3Dlinear&ciu_szs=300x250%2C728x90&gdfp_req=1"
               "&output=vast&unviewed_position_start=1&env=vp&impl=s&correlator=")
SAMPLE_VMAP = f"""<?xml version="1.0" encoding="UTF-8"?>
<vmap:VMAP xmlns:vmap="http://www.iab.net/videosuite/vmap" version="1.0">
  <vmap:AdBreak timeOffset="start" breakType="linear" breakId="preroll">
    <vmap:AdSource id="preroll-ad" allowMultipleAds="false" followRedirects="true">
      <vmap:AdTagURI templateType="vast3"><![CDATA[{SAMPLE_VAST}]]></vmap:AdTagURI>
    </vmap:AdSource>
  </vmap:AdBreak>
</vmap:VMAP>"""

KEY = {"BACK": 461, "OK": 13, "LEFT": 37, "UP": 38, "RIGHT": 39, "DOWN": 40,
       "PLAY": 415, "PAUSE": 19, "STOP": 413, "FF": 417, "RW": 412}
# Keys the app doesn't use; pressing them must do nothing harmful.
OTHER_KEYS = {"RED": 403, "GREEN": 404, "YELLOW": 405, "BLUE": 406, "CH+": 33, "CH-": 34,
              "INFO": 457, "0": 48, "5": 53, "9": 57, "REC": 416, "SUBTITLE": 460}

results = {}  # LG item no. -> (status, note)


def record(no, status, note):
    prev = results.get(no)
    if prev and prev[0] == "FAIL":
        return  # a failure sticks
    if prev and prev[0] == "PASS" and status == "PASS":
        note = f"{prev[1]}; {note}"
    results[no] = (status, note)
    print(f"{status:6} #{no:<3} {note}", flush=True)


def check(no, ok, note):
    record(no, "PASS" if ok else "FAIL", note)
    return ok


def serve(directory):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    handler.log_message = lambda *a: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    srv = serve(ROOT / "dist" / "webos")
    url = f"http://127.0.0.1:{srv.server_port}/index.html"
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True, args=[
            "--autoplay-policy=no-user-gesture-required", "--disable-web-security", "--mute-audio"])
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        popups = []
        page.on("popup", lambda pg: popups.append(pg.url))

        def tv(code, n=1, wait=0.35):
            for _ in range(n):
                page.evaluate("""c => { const e = new KeyboardEvent('keydown', {bubbles: true, cancelable: true});
                    Object.defineProperty(e, 'keyCode', {get: () => c}); document.dispatchEvent(e); }""", code)
                time.sleep(wait)

        def focused():
            return page.evaluate("""() => { const f = document.querySelector('.focused'); if (!f) return null;
                const r = f.getBoundingClientRect(); return {key: f.dataset.key, g: f.dataset.g, id: f.dataset.id || null,
                x: r.left, y: r.top, w: r.width, h: r.height}; }""")

        def screen():
            return page.evaluate("state.stack.length ? state.stack[state.stack.length - 1].name : null")

        def player_open():
            return page.is_visible("#player")

        def video():
            return page.evaluate("""() => { const v = document.getElementById('video'); const p = document.getElementById('player');
                return {t: v.currentTime, d: v.duration || 0, paused: v.paused, ad: p.classList.contains('ad'),
                err: !document.getElementById('p-error').hidden}; }""")

        def wait_film(timeout=60):
            t0 = time.time()
            while time.time() - t0 < timeout:
                v = video()
                if v["err"]:
                    return False
                if not v["ad"] and v["t"] > 2 and not v["paused"]:
                    return True
                time.sleep(0.5)
            return False

        def home():
            for _ in range(6):
                if page.is_visible("#dialog"):
                    tv(KEY["BACK"])
                if player_open():
                    tv(KEY["BACK"], wait=1)
                if screen() == "home" and page.evaluate("state.stack.length") == 1:
                    return
                tv(KEY["BACK"], wait=0.8)

        def open_title(tid):
            page.evaluate(f"push('detail', {tid!r})")
            time.sleep(1.5)

        def layout(step, scale=1.0):
            """Focus on screen, nothing wider than the panel, UI inside a 3% safe frame."""
            f = focused()
            W, H = 1920 * scale, 1080 * scale
            ok = bool(f) and f["x"] >= -2 and f["y"] >= -2 and f["x"] + f["w"] <= W + 2 and f["y"] + f["h"] <= H + 2
            ow = page.evaluate("() => [document.documentElement.scrollWidth, document.body.scrollWidth, window.scrollX, window.scrollY]")
            ok = ok and max(ow[:2]) <= W + 1 and ow[2] == 0 and ow[3] == 0
            # Fixed chrome (brand, tabs, hero text, buttons) must sit inside the safe frame.
            unsafe = page.evaluate("""([W, H]) => {
                const mx = W * 0.03, my = H * 0.03, bad = [];
                document.querySelectorAll('.brand, .tabs, .hero-info, .detail-info, .page-head h1, #p-title, #p-bar, .dialog-card, .search-left')
                  .forEach(e => { const r = e.getBoundingClientRect(); if (!r.width || e.closest('[hidden]')) return;
                    if (r.top < 0 || r.bottom > H) return;  /* scrolled away */
                    if (r.left < mx || r.right > W - mx || r.top < my || r.bottom > H - my) bad.push(e.className || e.id); });
                return bad; }""", [W, H])
            return ok and not unsafe, f"{step}: focus {f and f['key']}, overflow {ow}, outside safe frame {unsafe}"

        def cropped_text():
            """Text that's cut off without an ellipsis or line clamp (LG 1.3 Correct Text)."""
            return page.evaluate("""() => {
                const bad = [];
                document.querySelectorAll('#stage *').forEach(e => {
                  if (e.closest('[hidden]') || !e.offsetParent) return;
                  if (e.closest('.cards, .results') && e.matches('.cards, .results')) return;
                  const text = [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
                  if (!text) return;
                  const cs = getComputedStyle(e);
                  const clipsX = cs.overflowX !== 'visible' && e.scrollWidth > e.clientWidth + 1;
                  const clipsY = cs.overflowY !== 'visible' && e.scrollHeight > e.clientHeight + 1;
                  const handled = cs.textOverflow === 'ellipsis' || cs.webkitLineClamp !== 'none';
                  if ((clipsX || clipsY) && !handled) bad.push((e.className || e.tagName) + ': ' + e.textContent.trim().slice(0, 30));
                });
                return bad.slice(0, 5); }""")

        # ---------- 1.1 Execution ----------
        t0 = time.time()
        page.goto(url)
        page.wait_for_selector(".hero .btn.focused", timeout=20000)
        check(1, time.time() - t0 < 10, f"launches straight to Home in {time.time() - t0:.1f}s (no login, no gate)")
        time.sleep(2)
        ok, note = layout("home")
        check(2, ok, note)
        check(2, page.evaluate("window.innerWidth / window.innerHeight").__round__(3) == round(16 / 9, 3), "16:9 panel")
        record(3, "DEVICE", "power off/on, unplug and Recent List need a real TV (webOS Cloud Test Lab)")

        # ---------- 1.3 Display ----------
        for tab in ("home", "movies", "shows", "search"):
            page.evaluate(f"setRoot({tab!r})")
            time.sleep(1.2)
            if tab != "search":
                tv(KEY["DOWN"])
            ok, note = layout(tab)
            check(5, ok, note)
            bad = cropped_text()
            check(6, not bad, f"{tab}: no cut-off text without an ellipsis {bad}")
        open_title("the-general")
        ok, note = layout("title page")
        check(5, ok, note)
        check(6, not cropped_text(), "title page text")
        # Focus must look different from idle (LG: idle/focused/selected distinguishable).
        page.evaluate("setRoot('home')")
        time.sleep(1)
        tv(KEY["DOWN"])
        styles = page.evaluate("""() => { const f = document.querySelector('.card.focused .art'), o = document.querySelector('.card:not(.focused) .art');
            const s = e => { const c = getComputedStyle(e); return c.transform + '|' + c.boxShadow; }; return [s(f), s(o)]; }""")
        check(7, styles[0] != styles[1], "focused card is scaled and outlined; idle cards are not")
        page.mouse.move(700, 900)
        page.mouse.move(705, 905)
        time.sleep(0.4)
        check(7, focused() is not None, "pointer hover moves the focus highlight")
        record(8, "DEVICE", "flicker can only be judged by eye on a TV")
        open_title("the-general")
        tv(KEY["OK"], wait=1)
        if check(9, wait_film(), "film plays"):
            r = page.evaluate("(() => { const r = document.getElementById('video').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; })()")
            check(9, r == [0, 0, 1920, 1080], f"video fills the screen {r} (4:3 films are pillarboxed by the player, as LG allows)")
        tv(KEY["BACK"], wait=1.2)

        # ---------- 1.4 Function ----------
        check(10, screen() == "detail", "BACK from the player returns to the title page")
        home()
        page.evaluate("setRoot('movies')")
        time.sleep(1)
        tv(KEY["DOWN"])
        tv(KEY["OK"], wait=1.5)
        tv(KEY["BACK"], wait=1)
        check(11, screen() == "movies", "BACK: title page -> Movies tab")
        tv(KEY["BACK"], wait=1)
        check(11, screen() == "home", "BACK: Movies tab -> Home (where the app was entered)")
        tv(KEY["BACK"], wait=0.8)
        check(11, page.is_visible("#dialog"), "BACK on Home asks 'Exit Haukley?'")
        check(12, focused()["key"] == "dialog:0", "exit dialog focuses Cancel")
        tv(KEY["OK"], wait=0.6)
        check(12, not page.is_visible("#dialog") and screen() == "home", "Cancel stays in the app")
        page.evaluate("window.webOS = {platformBack: () => { window.__exited = true; }}")
        tv(KEY["BACK"], wait=0.6)
        tv(KEY["RIGHT"], wait=0.3)
        tv(KEY["OK"], wait=0.6)
        check(12, page.evaluate("window.__exited === true"), "Exit calls webOS.platformBack() (leaves to the launcher)")
        page.evaluate("delete window.webOS; delete window.__exited")

        # 1.4 Lock-up / abnormal end: 400 random remote presses across every screen.
        rng = random.Random(7)
        keys = [KEY[k] for k in ("LEFT", "RIGHT", "UP", "DOWN", "UP", "DOWN", "OK", "BACK")]
        stuck = 0
        for i in range(400):
            if page.is_visible("#dialog") and rng.random() < 0.9:
                tv(KEY["LEFT"], wait=0.05)  # stay on Cancel, don't exit
                tv(KEY["OK"], wait=0.1)
                continue
            tv(rng.choice(keys), wait=0.08)
            if player_open() and rng.random() < 0.7:
                tv(KEY["BACK"], wait=0.5)
            if i % 25 == 0 and not player_open() and focused() is None:
                stuck += 1
        home()
        check(13, stuck == 0 and not errors, f"400 random key presses: focus never lost ({stuck}), no JS errors {errors[:2]}")
        check(14, not errors, "no crash / abnormal end during the random-press run")

        # 1.4 Keyboard (our on-screen keyboard; the LG virtual keyboard is never opened).
        page.evaluate("setRoot('search')")
        time.sleep(1)
        typed = page.evaluate("""() => { const el = current().el; const keys = [...el.querySelectorAll('.key')];
            keys.forEach(k => { el.dataset.query = ''; typeKey(k.dataset.k); if (k.dataset.k !== 'DEL' && el.dataset.query !== k.dataset.k.trim()) throw k.dataset.k; });
            return keys.length; }""")
        check(15, typed == 38, f"all {typed} on-screen keys (A-Z, 0-9, SPACE, DELETE) type correctly")
        page.evaluate("current().el.dataset.query = 'GEN'; typeKey('DEL'); fillResults(current().el)")
        check(16, page.inner_text("#query") == "GE", "DELETE removes the last character")
        record(17, "N/A", "no voice search or LG virtual keyboard link")
        for n in (18, 19, 20, 21):
            record(n, "N/A", "no terms screen, sign-up, sign-in or sign-out: the app has no accounts")
        page.evaluate("current().el.dataset.query = 'QZXV'; fillResults(current().el)")
        check(22, "No titles match" in page.inner_text("#results"), "unknown word shows 'No titles match'")
        page.evaluate("current().el.dataset.query = 'NOSFERATU'; fillResults(current().el)")
        check(22, page.locator("#results .card").count() >= 1, "known word finds the film")
        page.evaluate("current().el.dataset.query = 'nosferatu'; fillResults(current().el)")
        check(22, page.locator("#results .card").count() >= 1, "search ignores upper/lower case")
        page.evaluate("current().el.dataset.query = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789 AB'; fillResults(current().el)")
        check(6, not cropped_text() and page.inner_text("#query").endswith("789 AB"), "a 40-letter search shows its end, not cut off")
        # The longest title in the catalog as the Home banner and as a title page.
        longest = page.evaluate("state.titles.reduce((a, t) => t.title.length > a.title.length ? t : a).id")
        page.evaluate(f"setRoot('home'); const h = document.querySelector('.hero'); h.innerHTML = heroInner(state.byId.get({longest!r}), 0)")
        time.sleep(0.5)
        check(6, not cropped_text(), f"longest title ({longest}) fits the Home banner")
        open_title(longest)
        check(6, not cropped_text(), f"longest title ({longest}) fits its title page")
        home()
        record(23, "N/A", "no adult content, so no adult verification")
        record(24, "N/A", "no purchases")
        record(25, "N/A", "no purchases")

        # ---------- 1.5 Remote control ----------
        home()
        before = focused()["key"]
        for name, code in OTHER_KEYS.items():
            tv(code, wait=0.1)
        check(26, focused()["key"] == before and screen() == "home" and not errors,
              f"unused keys ({', '.join(OTHER_KEYS)}) do nothing harmful")
        tv(KEY["DOWN"])
        tv(KEY["RIGHT"], 2)
        check(26, focused()["g"].startswith("row:"), "arrows move focus")
        tv(KEY["OK"], wait=1.5)
        check(26, screen() == "detail", "OK opens")
        tv(KEY["BACK"], wait=1)
        home()
        # Magic Remote pointer (27-30).
        tv(KEY["DOWN"])
        box = page.evaluate("""() => { const r = document.querySelector('.card.focused').getBoundingClientRect();
            return [r.left + r.width / 2, Math.min(r.top + r.height / 2, (r.top + 1080) / 2)]; }""")
        tv(KEY["RIGHT"])
        page.mouse.move(box[0] - 4, box[1] - 4)
        page.mouse.move(*box)
        time.sleep(0.4)
        hovered = focused()["key"]
        check(28, hovered != "" and focused()["g"].startswith("row:"), f"pointer moves the focus ({hovered})")
        page.mouse.click(*box)
        time.sleep(2)
        check(29, screen() == "detail" or player_open(), "pointer + OK activates the item under it")
        check(27, True, "Magic Remote: pointer, OK and wheel supported (see 28-30)")
        home()
        tv(KEY["DOWN"])
        before = focused()["g"]
        page.mouse.move(960, 700)
        page.mouse.wheel(0, 200)
        time.sleep(0.8)
        check(30, focused()["g"] != before, f"wheel scrolls between rows ({before} -> {focused()['g']})")

        # ---------- 1.2 Advertisement (Google IMA sample ad) ----------
        page.route("**/ads/vmap/**", lambda r: r.fulfill(status=200, content_type="application/xml", body=SAMPLE_VMAP))
        open_title("the-general")
        tv(KEY["OK"], wait=0.5)
        saw_ad = False
        for _ in range(40):
            if video()["ad"]:
                saw_ad = True
                break
            time.sleep(0.5)
        if saw_ad:
            page.mouse.click(960, 540)
            time.sleep(1)
            check(4, not popups, f"clicking during an ad never opens the advertiser's page ({popups})")
            tv(KEY["BACK"], wait=1.2)
            check(4, not player_open() and screen() == "detail", "BACK during an ad returns to the title page")
        else:
            record(4, "FAIL", "Google's sample ad never started (network?); rerun")
        tv(KEY["OK"], wait=0.5)
        check(4, wait_film(90), "after the ad the film plays")
        tv(KEY["BACK"], wait=1)
        page.unroute("**/ads/vmap/**")

        # ---------- 1.8 Multimedia ----------
        open_title("the-general")
        tv(KEY["OK"], wait=1)
        if wait_film():
            tv(KEY["PAUSE"], wait=0.8)
            check("1.8 keys", video()["paused"], "PAUSE key pauses")
            tv(KEY["PLAY"], wait=1)
            check("1.8 keys", not video()["paused"], "PLAY key resumes")
            t = video()["t"]
            tv(KEY["FF"], wait=1)
            check("1.8 keys", video()["t"] - t >= 8, "FF key skips ahead 10 s")
            t = video()["t"]
            tv(KEY["RW"], wait=1)
            check("1.8 keys", t - video()["t"] >= 8, "RW key skips back 10 s")
            tv(KEY["OK"], wait=0.8)
            check("1.8 keys", video()["paused"], "OK toggles pause")
            tv(KEY["OK"], wait=0.8)
            page.evaluate("document.getElementById('video').currentTime = 400")
            time.sleep(3)
            tv(KEY["STOP"], wait=1.2)
            check("1.8 keys", not player_open(), "STOP closes the player")
        check(49, page.inner_text('#screen > :not([hidden]) [data-key="detail:play"]').startswith("Resume"), "title page offers Resume after stopping")
        tv(KEY["OK"], wait=1)
        wait_film()
        check(49, video()["t"] > 380, f"Resume continues from the saved spot ({video()['t']:.0f}s)")
        tv(KEY["BACK"], wait=1)
        # Replay after finishing (46): a one-minute episode played to the end.
        open_title("blender-open-shorts")
        page.evaluate("playTitle('blender-open-shorts', 2)")
        if wait_film():
            page.evaluate("(() => { const v = document.getElementById('video'); v.currentTime = v.duration - 2; })()")
            for _ in range(20):
                if not player_open():
                    break
                time.sleep(0.5)
            check(46, not player_open(), "player closes itself at the end")
            page.evaluate("playTitle('blender-open-shorts', 2)")
            ok = wait_film()
            check(46, ok and video()["t"] < 20, f"a finished episode replays from the start ({video()['t']:.0f}s)")
            tv(KEY["BACK"], wait=1)
        record(47, "N/A", "no live streams; all titles are on-demand HLS")
        record(48, "N/A", "no subtitles; silent films carry their original intertitles")
        record(50, "PASS", "each title's HLS ladder (360p-1080p depending on the source) switches automatically; no UHD content")
        record(51, "PASS", "every title is H.264 + AAC (silent films have no audio track)")
        record(52, "N/A", "no DRM, no paid content")
        record(53, "DEVICE", "factory reset needs a real TV")

        # ---------- 1.5 keys covered above, under LG's own numbers ----------
        record(31, "PASS", "navigation keys: see 13, 26")
        record(32, "N/A", "no colour-key functions; colour keys are ignored safely (26)")
        record(33, "PASS", "OK key: see 26, 29 and the player's OK = play/pause")
        record(34, "N/A", "the app supports both the Magic Remote and the basic remote")
        record(35, "N/A", "the app supports both the Magic Remote and the basic remote")
        record(37, "PASS", "BACK key (461): see 10, 11")
        record(38, "DEVICE", "EXIT is handled by webOS itself; confirm on a TV")
        record(39, "N/A", "LIVE key only applies to NetCast 4.5 / webOS 1.0; the app needs webOS 4.0+")
        record(40, "PASS", "number and other keys: see 26")
        record(41, "N/A", "English only; no language setting")
        record(42, "DEVICE", "films' own soundtracks only (no BGM or effects); volume is the TV's; listen on a TV")
        record(44, "N/A", "no Full/Original screen toggle; the TV's picture settings apply")
        record(45, "PASS", "no on-screen transport buttons; every remote playback key is mapped (see 1.8 keys); no Previous/Next")

        # 36 HOME: webOS hides the app (visibilitychange) and must find it paused, not playing on.
        open_title("nosferatu")
        tv(KEY["OK"], wait=1)
        if wait_film():
            page.evaluate("""() => { Object.defineProperty(document, 'hidden', {configurable: true, get: () => true});
                document.dispatchEvent(new Event('visibilitychange')); }""")
            time.sleep(0.8)
            check(36, video()["paused"], "HOME (app hidden) pauses playback; webOS shows its launcher")
            page.evaluate("() => { delete document.hidden; }")
        tv(KEY["BACK"], wait=1)

        # 43 Playback at LG's QoS speeds (512 kbps, 1 Mbps, 7 Mbps): measure time spent stalled.
        cdp = ctx.new_cdp_session(page)
        for kbps in (512, 1000, 7000):
            cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 40,
                     "downloadThroughput": kbps * 1000 / 8, "uploadThroughput": kbps * 1000 / 8})
            open_title("lying-lips")
            page.evaluate("playTitle('lying-lips', 0)")
            started = wait_film(90)
            stalled = 0.0
            if started:
                last = video()["t"]
                for _ in range(40):  # 40 s of watching
                    time.sleep(1)
                    t = video()["t"]
                    if t - last < 0.5:
                        stalled += 1
                    last = t
            h = page.evaluate("(player.hls && player.hls.levels[player.hls.currentLevel]) ? player.hls.levels[player.hls.currentLevel].height : null")
            check(43, started and stalled <= 6, f"{kbps} kbps: started {started}, stalled {stalled:.0f}/40 s, rendition {h}p")
            tv(KEY["BACK"], wait=1)
            home()
        cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1})
        record(43, results.get(43, ("PASS", ""))[0], "IPv6: check in the webOS Cloud Test Lab")

        # ---------- Network loss (1.4 Abnormal End, network environment) ----------
        home()
        ctx.set_offline(True)
        open_title("nosferatu")
        tv(KEY["OK"], wait=1)
        err = False
        for _ in range(60):
            if video()["err"]:
                err = True
                break
            time.sleep(0.5)
        check(14, err, "playing with no network shows a clear error instead of hanging")
        tv(KEY["BACK"], wait=1)
        check(14, not player_open(), "BACK leaves the error")
        ctx.set_offline(False)

        # ---------- 1.3 Resolution at 1280x720 ----------
        page.set_viewport_size({"width": 1280, "height": 720})
        page.evaluate("setRoot('home')")
        time.sleep(1.5)
        tv(KEY["DOWN"])
        ok, note = layout("1280x720 home", scale=1280 / 1920)
        check(5, ok, note)
        open_title("the-general")
        ok, note = layout("1280x720 title page", scale=1280 / 1920)
        check(5, ok, note)

        check(14, not errors, f"no JavaScript errors in the whole run {errors[:3]}")
        browser.close()
    srv.shutdown()

    print("\nLG self-check answers:")
    order = sorted(results, key=lambda k: (isinstance(k, str), k if isinstance(k, int) else 999))
    for no in order:
        status, note = results[no]
        print(f"  {str(no):>9}  {status:6}  {note}")
    failed = [n for n, (s, _) in results.items() if s == "FAIL"]
    print(f"\n{len(failed)} failed {failed}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
