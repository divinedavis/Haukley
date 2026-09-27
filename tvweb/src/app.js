// Haukley for LG webOS and Samsung Tizen TVs: the same catalog, rows and ad schedule as the
// Apple TV / Fire TV / Roku apps, driven entirely by the remote (arrows, OK, Back).
// Packaged by tvweb/build.sh into a webOS .ipk and a Tizen .wgt.
"use strict";

const LIVE_CATALOG = "https://haukley.com/watch/catalog/catalog.json";
const ART = "https://haukley.com/watch/catalog/";
const IMA_SDK = "https://imasdk.googleapis.com/js/sdkloader/ima3.js";
const ADS = {
  adTagTemplate: "https://haukley.com/ads/vmap/{TITLE_ID}.xml?kind={KIND}&c={CORRELATOR}",
  trackingUrl: "https://axgxpwgbpgcqjxoqwtnv.supabase.co/rest/v1/rpc/log_ad_events",
  // Publishable key: public by design; it can only call the rate-limited log_ad_events RPC.
  publishableKey: "sb_publishable_9VpZfDWrMK3orLITxhWZJw_kbAFdw90",
};
const PROGRESS_KEY = "haukley.progress.v1";
const UI_HIDE_MS = 4000;
const SEEK_S = 10;

const IS_TIZEN = typeof window.tizen !== "undefined";
const IS_WEBOS = typeof window.PalmSystem !== "undefined" || /web0s|webos/i.test(navigator.userAgent);
// Ad events are only counted from the real TV apps, so local test runs don't pollute payouts.
const PLATFORM = IS_TIZEN ? "samsung" : IS_WEBOS ? "lg" : null;

const K = {
  LEFT: 37, UP: 38, RIGHT: 39, DOWN: 40, ENTER: 13,
  BACK: [461, 10009, 8, 27],
  PLAY: [415], PAUSE: [19], PLAYPAUSE: [10252, 179], STOP: [413], FF: [417, 228], RW: [412, 227],
};

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const art = (id, kind) => `${ART}${encodeURIComponent(id)}/${kind}.jpg`;
const bg = url => `style="background-image:url('${esc(url)}')"`;
const ICON = {
  play: '<svg viewBox="0 0 24 24"><path d="M7 4.5v15a1 1 0 0 0 1.5.86l12.5-7.5a1 1 0 0 0 0-1.72L8.5 3.64A1 1 0 0 0 7 4.5z"/></svg>',
  info: '<svg viewBox="0 0 24 24"><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm1 15h-2v-6h2zm0-8h-2V7h2z"/></svg>',
  restart: '<svg viewBox="0 0 24 24"><path d="M12 5V2L7 6l5 4V7a5 5 0 1 1-5 5H5a7 7 0 1 0 7-7z"/></svg>',
};

const state = {
  titles: [], byId: new Map(), rows: [], featured: [],
  stack: [],          // screens, top = current; each { name, el, focusKey }
  focused: null,
  homeDirty: false,
  lastIndex: {},      // group -> index last focused in it
};

/* ---------- catalog ---------- */

function fetchJson(url, ms) {
  return new Promise((resolve, reject) => {
    const ctl = typeof AbortController !== "undefined" ? new AbortController() : null;
    const timer = setTimeout(() => { if (ctl) ctl.abort(); reject(new Error("timeout")); }, ms);
    fetch(url, { cache: "no-store", signal: ctl ? ctl.signal : undefined })
      .then(r => { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
      .then(j => { clearTimeout(timer); resolve(j); }, e => { clearTimeout(timer); reject(e); });
  });
}

// The live catalog first (new films appear without an app update), else the packaged copy.
function loadCatalog() {
  const valid = c => c && Array.isArray(c.titles) && c.titles.length && Array.isArray(c.rows);
  return fetchJson(LIVE_CATALOG, 8000)
    .then(c => { if (!valid(c)) throw new Error("bad catalog"); return c; })
    .catch(() => fetchJson("catalog.json", 8000))
    .then(cat => {
      if (!valid(cat)) return false;
      state.titles = cat.titles.filter(t => t.stream);
      state.byId = new Map(state.titles.map(t => [t.id, t]));
      state.rows = cat.rows
        .map(r => Object.assign({}, r, { items: r.ids.map(id => state.byId.get(id)).filter(Boolean) }))
        .filter(r => r.items.length);
      state.featured = (cat.featured || []).map(id => state.byId.get(id)).filter(Boolean);
      if (!state.featured.length) state.featured = state.titles.slice(0, 5);
      return true;
    })
    .catch(() => false);
}

/* ---------- progress (Continue Watching) ---------- */

function readProgress() {
  try { return JSON.parse(localStorage.getItem(PROGRESS_KEY)) || {}; } catch (e) { return {}; }
}
function saveProgress(id, position, duration) {
  if (!(duration > 0) || !(position >= 0)) return;
  const all = readProgress();
  if (position > duration * 0.95) delete all[id];
  else all[id] = { p: Math.floor(position), d: Math.floor(duration), at: Date.now() };
  try { localStorage.setItem(PROGRESS_KEY, JSON.stringify(all)); } catch (e) {}
  state.homeDirty = true;
}
function resumeFor(id) {
  const r = readProgress()[id];
  return r && r.p > 30 && r.p < r.d * 0.95 ? r : null;
}
function continueWatching() {
  const all = readProgress();
  return Object.keys(all)
    .map(id => ({ t: state.byId.get(id), r: all[id] }))
    .filter(x => x.t && x.r.p > 30 && x.r.p < x.r.d * 0.95)
    .sort((a, b) => b.r.at - a.r.at)
    .slice(0, 10);
}

/* ---------- rendering ---------- */

const pad = n => (n < 10 ? "0" : "") + n;
function fmt(s) {
  s = Math.max(0, Math.floor(s || 0));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  return h ? `${h}:${pad(m)}:${pad(sec)}` : `${m}:${pad(sec)}`;
}
function metaLine(t) {
  const bits = [t.genre, t.year, t.runtime].filter(Boolean).map(esc).join(" · ");
  return `${bits}${t.rating ? `<span class="rating">${esc(t.rating === "NR" ? "NR" : t.rating)}</span>` : ""}`;
}
const FONTS = ["AbrilFatface", "Anton", "ArchivoBlack", "BebasNeue", "Cinzel", "Monoton", "Montserrat", "Oswald", "Pacifico", "PlayfairDisplay"];
function artTitle(t, cls) {
  const f = FONTS.indexOf(t.font) >= 0 ? t.font : "Montserrat"; // only the fonts bundled in fonts/
  return `<div class="art-title f-${f} ${cls}" style="font-family:'${f}'">${esc(t.title)}</div>`;
}

function topbar(active) {
  const tab = (key, label) => `<div class="tab nav${key === active ? " selected" : ""}" data-g="tabs" data-col="*" data-top="1" data-action="tab" data-tab="${key}" data-key="tab:${key}">${label}</div>`;
  return `<div class="topbar"><div class="brand">Haukley<b>.</b></div>
    <div class="tabs">${tab("home", "Home")}${tab("movies", "Movies")}${tab("search", "Search")}</div></div>`;
}

function cardHtml(t, type, rowKey, i, extra, group) {
  extra = extra || {};
  const key = `${rowKey}:${t.id}:${i}`;
  const g = `data-g="${esc(group || `row:${rowKey}`)}"${group ? ' data-col="right"' : ""}`;
  if (type === "ranked") {
    return `<div class="card ranked nav" ${g} data-action="title" data-id="${esc(t.id)}" data-key="${esc(key)}">
      <div class="rank">${i + 1}</div><div class="art" ${bg(art(t.id, "poster"))}></div></div>`;
  }
  if (type === "poster") {
    return `<div class="card poster nav" ${g} data-action="title" data-id="${esc(t.id)}" data-key="${esc(key)}">
      <div class="art" ${bg(art(t.id, "poster"))}></div></div>`;
  }
  const progress = extra.progress != null ? `<div class="progress"><i style="width:${Math.max(3, Math.round(extra.progress * 100))}%"></i></div>` : "";
  return `<div class="card nav" ${g} data-action="${extra.play ? "play" : "title"}" data-id="${esc(t.id)}" data-key="${esc(key)}">
    <div class="art" ${bg(art(t.id, "card"))}>${progress}</div>
    <div class="label">${esc(t.title)}</div><div class="sub">${esc(extra.sub || `${t.genre} · ${t.year}`)}</div></div>`;
}

function rowHtml(key, title, type, items, extra = () => ({})) {
  return `<section class="row" data-row="${esc(key)}"><h3>${esc(title)}</h3>
    <div class="track"><div class="cards">${items.map((t, i) => cardHtml(t, type, key, i, extra(t, i))).join("")}</div></div></section>`;
}

function cwRowHtml() {
  const cw = continueWatching();
  if (!cw.length) return "";
  const byT = new Map(cw.map(x => [x.t.id, x.r]));
  return rowHtml("continue", "Continue Watching", "card", cw.map(x => x.t), t => {
    const r = byT.get(t.id);
    return { progress: r.p / r.d, play: true, sub: `${Math.max(1, Math.round((r.d - r.p) / 60))} min left` };
  });
}

function heroInner(t, index) {
  const resume = resumeFor(t.id);
  return `<div class="hero-bg" ${bg(art(t.id, "backdrop"))}></div>
    <div class="hero-info">
      <div class="eyebrow">NOW STREAMING FREE</div>
      ${artTitle(t, "hero-title")}
      <div class="meta">${metaLine(t)}</div>
      <div class="desc">${esc(t.description)}</div>
      <div class="buttons">
        <div class="btn nav" data-g="hero" data-action="play" data-id="${esc(t.id)}" data-key="hero:play">${ICON.play}${resume ? "Resume" : "Play"}</div>
        <div class="btn nav" data-g="hero" data-action="title" data-id="${esc(t.id)}" data-key="hero:info">${ICON.info}More Info</div>
      </div>
    </div>
    <div class="dots">${state.featured.map((_, i) => `<div class="dot${i === index ? " on" : ""}"></div>`).join("")}</div>`;
}

function renderHome() {
  const el = document.createElement("div");
  el.className = "scroller";
  el.innerHTML = `<div class="page" data-vscroll>
      ${topbar("home")}
      <div class="hero" data-hero="0">${heroInner(state.featured[0], 0)}</div>
      <div class="rows">${cwRowHtml()}${state.rows.map(r => rowHtml(r.key, r.title, r.type === "ranked" ? "ranked" : r.type === "poster" ? "poster" : "card", r.items)).join("")}</div>
    </div>`;
  return el;
}

function renderMovies() {
  const genres = new Map();
  for (const t of state.titles) {
    if (!genres.has(t.genre)) genres.set(t.genre, []);
    genres.get(t.genre).push(t);
  }
  const rows = [...genres.entries()].sort((a, b) => b[1].length - a[1].length);
  const el = document.createElement("div");
  el.className = "scroller";
  el.innerHTML = `<div class="page" data-vscroll>
      ${topbar("movies")}
      <div class="page-head"><h1>Movies</h1><p>${state.titles.length} free films, every one ready to stream.</p></div>
      <div class="rows">${rows.map(([g, list]) => rowHtml(`genre-${g}`, g, "poster", list.sort((a, b) => a.title.localeCompare(b.title)))).join("")}</div>
    </div>`;
  return el;
}

function renderDetail(id) {
  const t = state.byId.get(id);
  const resume = resumeFor(id);
  let more = state.titles.filter(x => x.genre === t.genre && x.id !== id);
  if (more.length < 4) more = more.concat(state.featured.filter(x => x.id !== id && !more.includes(x)));
  more = more.slice(0, 12);
  const el = document.createElement("div");
  el.className = "scroller";
  el.innerHTML = `<div class="detail-bg" ${bg(art(id, "backdrop"))}></div>
    <div class="page" data-vscroll>
      <div class="detail-top"><div class="detail-info">
        ${artTitle(t, "detail-title")}
        <div class="meta">${metaLine(t)}${t.silent ? " · Silent film" : ""}</div>
        <div class="desc">${esc(t.description)}</div>
        ${t.credits ? `<div class="credits">${esc(t.credits)}</div>` : ""}
        <div class="buttons">
          <div class="btn nav" data-g="detail" data-top="1" data-action="play" data-id="${esc(id)}" data-key="detail:play">${ICON.play}${resume ? `Resume ${fmt(resume.p)}` : "Play"}</div>
          ${resume ? `<div class="btn nav" data-g="detail" data-top="1" data-action="restart" data-id="${esc(id)}" data-key="detail:restart">${ICON.restart}Start Over</div>` : ""}
        </div>
        ${t.license ? `<div class="license">${esc(t.license)}</div>` : ""}
      </div></div>
      <div class="rows">${rowHtml(`more-${id}`, "More Like This", "card", more)}</div>
    </div>`;
  return el;
}

const KEYBOARD = [
  ["A", "B", "C", "D", "E", "F"], ["G", "H", "I", "J", "K", "L"], ["M", "N", "O", "P", "Q", "R"],
  ["S", "T", "U", "V", "W", "X"], ["Y", "Z", "1", "2", "3", "4"], ["5", "6", "7", "8", "9", "0"],
];
const RESULT_COLS = 4;

function renderSearch() {
  const el = document.createElement("div");
  el.className = "search";
  el.dataset.query = "";
  el.innerHTML = `${topbar("search")}
    <div class="search-left">
      <div class="query empty" id="query">Search titles, genres, people</div>
      <div class="keys">
        ${KEYBOARD.map((row, r) => row.map(k => `<div class="key nav" data-g="keys:${r}" data-col="left" data-action="key" data-k="${k}" data-key="key:${k}">${k}</div>`).join("")).join("")}
        <div class="key wide nav" data-g="keys:6" data-col="left" data-action="key" data-k=" " data-key="key:space">SPACE</div>
        <div class="key wide nav" data-g="keys:6" data-col="left" data-action="key" data-k="DEL" data-key="key:del">DELETE</div>
      </div>
    </div>
    <div class="search-right"><div class="results" data-vscroll id="results"></div></div>`;
  fillResults(el);
  return el;
}

function searchMatches(q) {
  q = q.trim().toLowerCase();
  if (!q) return { heading: "Popular on Haukley", list: (state.rows[0] ? state.rows[0].items : state.featured) };
  const words = q.split(/\s+/);
  const list = state.titles.filter(t => {
    const hay = `${t.title} ${t.genre} ${t.credits || ""} ${t.year}`.toLowerCase();
    return words.every(w => hay.includes(w));
  });
  list.sort((a, b) => (b.title.toLowerCase().startsWith(q) ? 1 : 0) - (a.title.toLowerCase().startsWith(q) ? 1 : 0));
  return { heading: `Results for “${q}”`, list };
}

function fillResults(el) {
  const q = el.dataset.query;
  const box = $("#results", el);
  const qEl = $("#query", el);
  qEl.textContent = q || "Search titles, genres, people";
  qEl.classList.toggle("empty", !q);
  const { list } = searchMatches(q);
  if (!list.length) {
    box.innerHTML = `<div class="empty-note">No titles match “${esc(q.trim())}”. Try another word.</div>`;
    return;
  }
  box.innerHTML = list.map((t, i) => cardHtml(t, "poster", "res", i, null, `res:${Math.floor(i / RESULT_COLS)}`)).join("");
  box.style.transform = "";
}

/* ---------- screens ---------- */

function current() { return state.stack[state.stack.length - 1]; }

function show(entry, focusKey) {
  $$("#screen > *").forEach(n => { n.hidden = n !== entry.el; });
  if (!entry.el.parentNode) $("#screen").appendChild(entry.el);
  entry.el.hidden = false;
  const target = (focusKey && byKey(entry.el, focusKey)) || firstFocus(entry);
  focus(target, true);
}

function byKey(root, key) {
  const all = $$(".nav", root);
  for (let i = 0; i < all.length; i++) if (all[i].dataset.key === key) return all[i];
  return null;
}

function firstFocus(entry) {
  const pick = { home: '[data-key="hero:play"]', detail: '[data-key="detail:play"]', search: '[data-key="key:A"]', movies: ".rows .nav" }[entry.name];
  return (pick && entry.el.querySelector(pick)) || entry.el.querySelector(".nav");
}

function build(name, arg) {
  if (name === "home") return renderHome();
  if (name === "movies") return renderMovies();
  if (name === "search") return renderSearch();
  return renderDetail(arg);
}

function push(name, arg) {
  const cur = current();
  if (cur) cur.focusKey = state.focused && state.focused.dataset.key;
  const entry = { name, arg, el: build(name, arg), focusKey: null };
  state.stack.push(entry);
  show(entry);
  if (name === "home") startHeroRotation(entry);
}

function setRoot(name) {
  stopHeroRotation();
  state.stack.forEach(e => e.el.remove());
  state.stack = [];
  push(name);
  if (name !== "home") focus(byKey(current().el, `tab:${name}`), true);
}

function pop() {
  if (state.stack.length <= 1) {
    const root = current();
    if (root.name !== "home") return setRoot("home");
    return confirmExit();
  }
  const gone = state.stack.pop();
  gone.el.remove();
  const back = current();
  // Detail pages show Resume state; rebuild them (and Home's Continue Watching) after playback.
  if ((back.name === "home" && state.homeDirty) || back.name === "detail") {
    back.el.remove();
    back.el = build(back.name, back.arg);
    if (back.name === "home") state.homeDirty = false;
  }
  show(back, back.focusKey);
  if (back.name === "home") startHeroRotation(back);
}

/* ---------- hero rotation ---------- */

let heroTimer = null;
function startHeroRotation(entry) {
  stopHeroRotation();
  if (state.featured.length < 2) return;
  heroTimer = setInterval(() => {
    const hero = $(".hero", entry.el);
    if (!hero || entry.el.hidden || !$("#player").hidden || !$("#dialog").hidden) return;
    if (state.focused && hero.contains(state.focused)) return; // don't swap the film under the viewer
    const i = (Number(hero.dataset.hero) + 1) % state.featured.length;
    hero.dataset.hero = String(i);
    hero.innerHTML = heroInner(state.featured[i], i);
  }, 9000);
}
function stopHeroRotation() { clearInterval(heroTimer); heroTimer = null; }

/* ---------- focus + spatial navigation ---------- */

function scope() {
  if (!$("#dialog").hidden) return $("#dialog");
  return current().el;
}

// Every focusable carries data-g (its row/group) and optionally data-col (which column of
// groups it belongs to; "*" joins every column, e.g. the tab bar). Left/right walks a group,
// up/down jumps to the next group in the same column, in DOM order.
function focus(el, instant) {
  if (!el) return;
  if (state.focused) state.focused.classList.remove("focused");
  state.focused = el;
  el.classList.add("focused");
  state.lastIndex[el.dataset.g] = inGroup(el.dataset.g).indexOf(el);
  reveal(el, instant);
}

const navAll = () => $$(".nav", scope());
const inGroup = g => navAll().filter(n => n.dataset.g === g);
function groupOrder() {
  const seen = [];
  navAll().forEach(n => { if (seen.indexOf(n.dataset.g) < 0) seen.push(n.dataset.g); });
  return seen;
}
const colOf = g => { const n = inGroup(g)[0]; return (n && n.dataset.col) || "main"; };

function move(dir) {
  const cur = state.focused;
  if (!cur || !scope().contains(cur)) return focus(firstFocus(current()) || $(".nav", scope()));
  const g = cur.dataset.g;
  const items = inGroup(g);
  const i = items.indexOf(cur);
  if (dir === "left" || dir === "right") {
    const next = items[i + (dir === "right" ? 1 : -1)];
    return focus(next || nearestSideways(cur, dir));
  }
  const order = groupOrder();
  const gi = order.indexOf(g);
  const col = colOf(g);
  const step = dir === "down" ? 1 : -1;
  for (let j = gi + step; j >= 0 && j < order.length; j += step) {
    const c = colOf(order[j]);
    if (col === "*" || c === "*" || c === col) return focus(entryPoint(order[j], cur));
  }
}

// Moving up/down into a row: go back to where the viewer was in it if that's still on
// screen, else to the item closest to the current horizontal position.
function entryPoint(g, from) {
  const items = inGroup(g);
  const last = items[state.lastIndex[g]];
  if (last && g.indexOf("row:") === 0 && onScreen(last)) return last;
  const fx = centerX(from);
  let best = items[0], bestD = Infinity;
  items.forEach(it => {
    const d = Math.abs(centerX(it) - fx) + (onScreen(it) ? 0 : 5000);
    if (d < bestD) { best = it; bestD = d; }
  });
  return best;
}

function nearestSideways(cur, dir) {
  const c = cur.getBoundingClientRect();
  let best = null, bestD = Infinity;
  navAll().forEach(it => {
    if (it === cur) return;
    const r = it.getBoundingClientRect();
    if (Math.min(r.bottom, c.bottom) - Math.max(r.top, c.top) <= 0) return;
    const d = dir === "right" ? r.left - c.right : c.left - r.right;
    if (d < -1 || d >= bestD) return;
    best = it; bestD = d;
  });
  return best;
}

const stageScale = () => $("#stage").getBoundingClientRect().width / 1920;
function centerX(el) { const r = el.getBoundingClientRect(); return (r.left + r.width / 2) / stageScale(); }
function onScreen(el) {
  const r = el.getBoundingClientRect(), s = stageScale();
  return r.right / s > 0 && r.left / s < 1920 && r.bottom / s > 0 && r.top / s < 1080;
}

function translateOf(el, axis) {
  const m = /translate([XY])\((-?[\d.]+)px\)/.exec(el.style.transform || "");
  return m && m[1] === axis ? Number(m[2]) : 0;
}

// Keep the focused item on screen: rows slide sideways, pages slide up.
function reveal(el, instant) {
  const cards = el.closest(".cards");
  if (cards) {
    const track = cards.parentElement;
    const visible = track.clientWidth - 2 * 90;
    let x = -translateOf(cards, "X");
    const left = el.offsetLeft, right = left + el.offsetWidth;
    if (right - x > visible) x = right - visible;
    if (left < x) x = left;
    const max = Math.max(0, cards.scrollWidth - visible);
    x = Math.max(0, Math.min(x, max));
    setTransform(cards, `translateX(${-x}px)`, instant);
  }
  const page = el.closest("[data-vscroll]");
  if (page) {
    let y;
    if (el.dataset.top || el.closest(".hero")) y = 0;
    else if (page.id === "results") {
      const row = Math.floor($$(".nav", page).indexOf(el) / RESULT_COLS);
      y = Math.max(0, row - 1) * (345 + 36);
    } else {
      const section = el.closest(".row") || el;
      // The first row under a page heading stays put so the heading remains visible.
      y = section === $(".rows > .row", page) && $(".page-head", page) ? 0 : Math.max(0, offsetWithin(section, page) - 130);
    }
    setTransform(page, `translateY(${-y}px)`, instant);
  }
}
function offsetWithin(el, ancestor) {
  let y = 0;
  for (let n = el; n && n !== ancestor; n = n.offsetParent) y += n.offsetTop;
  return y;
}
function setTransform(el, value, instant) {
  if (instant) {
    el.style.transition = "none";
    el.style.transform = value;
    void el.offsetWidth;
    el.style.transition = "";
  } else {
    el.style.transform = value;
  }
}

/* ---------- actions ---------- */

function activate(el) {
  if (!el) return;
  const a = el.dataset.action, id = el.dataset.id;
  if (a === "tab") {
    const tab = el.dataset.tab;
    if (state.stack.length === 1 && current().name === tab) return;
    return setRoot(tab);
  }
  if (a === "title") return push("detail", id);
  if (a === "play") { const r = resumeFor(id); return startPlayback(id, r ? r.p : 0); }
  if (a === "restart") return startPlayback(id, 0);
  if (a === "key") return typeKey(el.dataset.k);
  if (a === "dialog") return el._run && el._run();
}

function typeKey(k) {
  const el = current().el;
  let q = el.dataset.query || "";
  if (k === "DEL") q = q.slice(0, -1);
  else if (q.length < 40) q = (q + k).replace(/^\s+/, "").replace(/\s{2,}/g, " ");
  el.dataset.query = q;
  fillResults(el);
}

/* ---------- dialog ---------- */

function dialog(title, text, buttons) {
  const d = $("#dialog");
  $("#dialog-title").textContent = title;
  $("#dialog-text").textContent = text;
  const box = $("#dialog-buttons");
  box.innerHTML = "";
  state.beforeDialog = state.focused;
  buttons.forEach((b, i) => {
    const n = document.createElement("div");
    n.className = "btn nav";
    n.dataset.action = "dialog";
    n.dataset.g = "dialog";
    n.dataset.key = `dialog:${i}`;
    n.textContent = b.label;
    n._run = () => { closeDialog(); b.run && b.run(); };
    box.appendChild(n);
  });
  d.hidden = false;
  focus(box.children[buttons.findIndex(b => b.focus) >= 0 ? buttons.findIndex(b => b.focus) : 0], true);
}
function closeDialog() {
  $("#dialog").hidden = true;
  const back = state.beforeDialog;
  state.beforeDialog = null;
  if (back && document.contains(back)) focus(back, true);
  else if (current()) focus(firstFocus(current()), true);
}

function confirmExit() {
  dialog("Exit Haukley?", "You can come back any time. Your Continue Watching list is saved.", [
    { label: "Cancel", focus: true },
    { label: "Exit", run: exitApp },
  ]);
}

function exitApp() {
  try {
    if (IS_TIZEN) return tizen.application.getCurrentApplication().exit();
  } catch (e) {}
  try {
    if (window.webOS && typeof window.webOS.platformBack === "function") return window.webOS.platformBack();
  } catch (e) {}
  window.close();
}

/* ---------- player ---------- */

const player = { el: null, video: null, id: null, ima: null, hls: null, uiTimer: null, saveTimer: null, sessionId: null };

function uuid() {
  if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
  return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, c =>
    (c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))).toString(16));
}

let imaPromise = null;
function loadIma() {
  if (window.google && google.ima) return Promise.resolve(true);
  if (!imaPromise) {
    imaPromise = new Promise(res => {
      const s = document.createElement("script");
      s.src = IMA_SDK;
      s.async = true;
      s.onload = () => res(Boolean(window.google && google.ima));
      s.onerror = () => { imaPromise = null; res(false); }; // offline: play without ads
      document.head.appendChild(s);
      setTimeout(() => res(Boolean(window.google && google.ima)), 6000);
    });
  }
  return imaPromise;
}

function logAdEvent(event) {
  if (!PLATFORM) return;
  const body = JSON.stringify({ title_id: player.id, episode: 0, platform: PLATFORM, event, session_id: player.sessionId });
  const send = () => fetch(ADS.trackingUrl, {
    method: "POST",
    headers: { apikey: ADS.publishableKey, "Content-Type": "application/json", Prefer: "return=minimal" },
    body,
  }).then(r => { if (!r.ok) throw new Error(String(r.status)); });
  send().catch(() => new Promise(r => setTimeout(r, 3000)).then(send)).catch(() => {});
}

// TVs play HLS natively in <video>; desktop browsers (used for testing) go through hls.js.
function attachSource(src, startAt) {
  const v = player.video;
  const native = v.canPlayType("application/vnd.apple.mpegurl");
  if ((IS_TIZEN || IS_WEBOS || !(window.Hls && Hls.isSupported())) && native) {
    v.src = src;
  } else if (window.Hls && Hls.isSupported()) {
    player.hls = new Hls({ startPosition: startAt || -1 });
    player.hls.on(Hls.Events.ERROR, (_, d) => { if (d.fatal) playerError(); });
    player.hls.loadSource(src);
    player.hls.attachMedia(v);
  } else {
    v.src = src;
  }
  if (startAt) {
    const jump = () => { v.removeEventListener("loadedmetadata", jump); if (v.currentTime < 1) v.currentTime = startAt; };
    v.addEventListener("loadedmetadata", jump);
  }
}

function startPlayback(id, startAt) {
  const t = state.byId.get(id);
  if (!t) return;
  stopPlayback();
  stopHeroRotation();
  Object.assign(player, { id, sessionId: uuid() });
  $("#p-title").textContent = t.title;
  $("#p-error").hidden = true;
  $("#p-state").textContent = "";
  player.el.hidden = false;
  player.el.classList.add("loading");
  player.el.classList.remove("ad");
  if (state.focused) state.focused.classList.remove("focused");
  attachSource(t.stream, startAt);
  loadIma().then(ok => {
    if (player.id !== id || player.el.hidden) return;
    if (ok) startAds(t);
    else player.video.play().catch(() => {});
  });
  player.saveTimer = setInterval(() => {
    const v = player.video;
    if (!v.paused && !(player.ima && player.ima.adPlaying)) saveProgress(id, v.currentTime, v.duration);
  }, 10000);
  pokeUi();
}

function adWarn(ev) {
  try { console.warn("IMA ad error:", ev.getError().toString()); } catch (e) {}
}

function startAds(t) {
  const ima = google.ima;
  const v = player.video;
  const s = { adPlaying: false, contentDone: false, manager: null, contentStarted: false };
  player.ima = s;
  const adLayer = $("#ad-layer");
  s.container = new ima.AdDisplayContainer(adLayer, v);
  s.container.initialize();
  s.loader = new ima.AdsLoader(s.container);
  const playContent = () => {
    s.contentStarted = true;
    s.adPlaying = false;
    player.el.classList.remove("ad");
    if (!s.contentDone) v.play().catch(() => {});
    pokeUi();
  };
  s.loader.addEventListener(ima.AdsManagerLoadedEvent.Type.ADS_MANAGER_LOADED, ev => {
    clearTimeout(s.timeout);
    if (s.contentStarted || player.ima !== s) return; // the timeout already started the film
    const settings = new ima.AdsRenderingSettings();
    settings.restoreCustomPlaybackStateOnAdBreakComplete = true;
    const m = ev.getAdsManager(v, settings);
    s.manager = m;
    const E = ima.AdEvent.Type;
    m.addEventListener(E.CONTENT_PAUSE_REQUESTED, () => {
      s.adPlaying = true;
      v.pause();
      player.el.classList.add("ad");
      player.el.classList.remove("loading");
    });
    m.addEventListener(E.CONTENT_RESUME_REQUESTED, playContent);
    m.addEventListener(E.STARTED, () => logAdEvent("ad_started"));
    m.addEventListener(E.COMPLETE, () => logAdEvent("ad_completed"));
    m.addEventListener(ima.AdErrorEvent.Type.AD_ERROR, ev => { adWarn(ev); playContent(); });
    try {
      m.init(1920, 1080, ima.ViewMode.FULLSCREEN);
      m.start();
    } catch (e) {
      playContent();
    }
  });
  s.loader.addEventListener(ima.AdErrorEvent.Type.AD_ERROR, ev => { adWarn(ev); playContent(); });
  v.addEventListener("ended", s.onEnded = () => { s.contentDone = true; s.loader.contentComplete(); });
  const req = new ima.AdsRequest();
  req.adTagUrl = ADS.adTagTemplate
    .replace("{TITLE_ID}", encodeURIComponent(t.id))
    .replace("{KIND}", t.kind)
    .replace("{CORRELATOR}", String(Date.now()));
  req.linearAdSlotWidth = req.nonLinearAdSlotWidth = 1920;
  req.linearAdSlotHeight = 1080;
  req.nonLinearAdSlotHeight = 150;
  s.loader.requestAds(req);
  // If the ad server never answers, start the film anyway.
  s.timeout = setTimeout(() => { if (!s.manager && player.ima === s) playContent(); }, 8000);
}

function stopPlayback() {
  const v = player.video;
  if (player.id && v.duration && !(player.ima && player.ima.adPlaying)) saveProgress(player.id, v.currentTime, v.duration);
  clearInterval(player.saveTimer);
  clearTimeout(player.uiTimer);
  if (player.ima) {
    clearTimeout(player.ima.timeout);
    try { if (player.ima.manager) player.ima.manager.destroy(); player.ima.loader.destroy(); player.ima.container.destroy(); } catch (e) {}
    v.removeEventListener("ended", player.ima.onEnded);
    player.ima = null;
  }
  if (player.hls) { player.hls.destroy(); player.hls = null; }
  v.pause();
  v.removeAttribute("src");
  try { v.load(); } catch (e) {}
  $("#ad-layer").innerHTML = "";
  player.id = null;
}

function closePlayer() {
  stopPlayback();
  player.el.hidden = true;
  // Rebuild the page under the player so Resume / Continue Watching are current.
  const cur = current();
  const key = state.focused && state.focused.dataset.key;
  if (cur.name === "detail" || (cur.name === "home" && state.homeDirty)) {
    cur.el.remove();
    cur.el = build(cur.name, cur.arg);
    if (cur.name === "home") state.homeDirty = false;
    show(cur, key);
  } else if (state.focused) {
    focus(state.focused, true);
  }
  if (cur.name === "home") startHeroRotation(cur);
}

function playerError(text) {
  const p = $("#p-error");
  p.textContent = text || "This film couldn't play. Check the TV's internet connection, then press BACK and try again.";
  p.hidden = false;
  player.el.classList.remove("loading");
}

function pokeUi() {
  const ui = $("#p-ui");
  ui.classList.remove("hide");
  clearTimeout(player.uiTimer);
  player.uiTimer = setTimeout(() => { if (!player.video.paused) ui.classList.add("hide"); }, UI_HIDE_MS);
}

function syncTime() {
  const v = player.video;
  const d = v.duration || 0, c = v.currentTime || 0;
  const pct = d ? (c / d) * 100 : 0;
  $("#p-fill").style.width = `${pct}%`;
  $("#p-knob").style.left = `${pct}%`;
  $("#p-cur").textContent = fmt(c);
  $("#p-dur").textContent = fmt(d);
}

function togglePlay() {
  const s = player.ima;
  if (s && s.adPlaying && s.manager) {
    s.paused = !s.paused;
    if (s.paused) s.manager.pause(); else s.manager.resume();
    return;
  }
  const v = player.video;
  if (v.paused) v.play().catch(() => {}); else v.pause();
  pokeUi();
}

function seek(delta) {
  if (player.ima && player.ima.adPlaying) return;
  const v = player.video;
  if (!v.duration) return;
  v.currentTime = Math.max(0, Math.min(v.duration - 1, v.currentTime + delta));
  $("#p-state").textContent = delta > 0 ? `» ${SEEK_S}s` : `« ${SEEK_S}s`;
  syncTime();
  pokeUi();
}

function playerKey(code) {
  if (K.BACK.includes(code) || K.STOP.includes(code)) return closePlayer();
  if (code === K.ENTER || K.PLAYPAUSE.includes(code)) return togglePlay();
  if (K.PLAY.includes(code)) { if (player.video.paused) togglePlay(); return; }
  if (K.PAUSE.includes(code)) { if (!player.video.paused) togglePlay(); return; }
  if (code === K.RIGHT || K.FF.includes(code)) return seek(SEEK_S);
  if (code === K.LEFT || K.RW.includes(code)) return seek(-SEEK_S);
  pokeUi();
}

/* ---------- input ---------- */

function onKey(e) {
  const code = e.keyCode;
  const handled = [K.LEFT, K.UP, K.RIGHT, K.DOWN, K.ENTER, ...K.BACK, ...K.PLAY, ...K.PAUSE, ...K.PLAYPAUSE, ...K.STOP, ...K.FF, ...K.RW].includes(code);
  if (!handled) return;
  e.preventDefault();
  if (!player.el.hidden && $("#dialog").hidden) return playerKey(code);
  if (K.BACK.includes(code)) {
    if (!$("#dialog").hidden) return closeDialog();
    return pop();
  }
  if (code === K.ENTER) return activate(state.focused);
  const dir = { 37: "left", 38: "up", 39: "right", 40: "down" }[code];
  if (dir) move(dir);
}

function registerTizenKeys() {
  if (!IS_TIZEN) return;
  try {
    tizen.tvinputdevice.registerKeyBatch(["MediaPlayPause", "MediaPlay", "MediaPause", "MediaStop", "MediaFastForward", "MediaRewind"]);
  } catch (e) {}
}

function fitStage() {
  const s = Math.min(window.innerWidth / 1920, window.innerHeight / 1080) || 1;
  $("#stage").style.transform = `scale(${s})`;
}

function boot() {
  fitStage();
  window.addEventListener("resize", fitStage);
  registerTizenKeys();
  player.el = $("#player");
  player.video = $("#video");
  const v = player.video;
  v.addEventListener("timeupdate", syncTime);
  v.addEventListener("playing", () => { player.el.classList.remove("loading"); $("#p-state").textContent = ""; pokeUi(); });
  v.addEventListener("waiting", () => player.el.classList.add("loading"));
  v.addEventListener("pause", () => { if (!(player.ima && player.ima.adPlaying) && player.id) { $("#p-state").textContent = "Paused"; pokeUi(); } });
  v.addEventListener("error", () => { if (player.id && !(player.ima && player.ima.adPlaying)) playerError(); });
  v.addEventListener("ended", () => {
    if (player.ima && player.ima.adPlaying) return;
    if (player.id) saveProgress(player.id, v.duration, v.duration);
    // Leave a moment for a post-roll; then return to the page.
    setTimeout(() => { if (player.id && v.ended) closePlayer(); }, 1500);
  });
  document.addEventListener("keydown", onKey);
  document.addEventListener("visibilitychange", () => { if (document.hidden && player.id) { const s = player.ima; if (!(s && s.adPlaying)) v.pause(); } });

  loadCatalog().then(ok => {
    if (ok) return setRoot("home");
    $("#screen").innerHTML = `<div class="offline"><div>Haukley can't reach the internet.</div><div class="offline-sub">Check the TV's network connection, then open Haukley again.</div></div>`;
  });
}

boot();
