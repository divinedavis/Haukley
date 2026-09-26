// Haukley web player. Signed-in viewers browse the same catalog as the TV and iPhone apps
// (built by scripts/make_web.py), play HLS with Google IMA ads, and sync Continue Watching
// and My List to Supabase (RLS: each viewer sees only their own rows).
"use strict";

const SUPABASE_URL = "https://axgxpwgbpgcqjxoqwtnv.supabase.co";
// Publishable key: public by design; every table it can reach is guarded by RLS.
const SUPABASE_KEY = "sb_publishable_9VpZfDWrMK3orLITxhWZJw_kbAFdw90";
const IMA_SDK = "https://imasdk.googleapis.com/js/sdkloader/ima3.js";
const ART = "catalog/";

const sb = supabase.createClient(SUPABASE_URL, SUPABASE_KEY, {
  auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true, flowType: "pkce" },
});

const $ = (sel, root = document) => root.querySelector(sel);
const app = $("#app");
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const state = {
  user: null,
  catalog: null,
  byId: new Map(),
  progress: new Map(), // "id:episode" -> { title_id, episode, position_s, duration_s, updated_at }
  myList: new Set(),
  ads: null,
  recovering: false,
  heroId: null,
  page: null, // hash of the page under the modal/player, to restore scroll when coming back
  modalPushed: false,
};

// ---------- data ----------

async function loadCatalog() {
  const [cat, ads] = await Promise.all([
    fetch(ART + "catalog.json").then(r => r.json()),
    fetch(ART + "ads.json").then(r => r.json()),
  ]);
  state.catalog = cat;
  state.ads = ads;
  state.byId = new Map(cat.titles.map(t => [t.id, t]));
}

async function loadViewerData() {
  const [p, l] = await Promise.all([
    sb.from("watch_progress").select("title_id,episode,position_s,duration_s,updated_at"),
    sb.from("my_list").select("title_id,added_at").order("added_at", { ascending: false }),
  ]);
  state.progress = new Map((p.data || []).map(r => [`${r.title_id}:${r.episode}`, r]));
  state.myList = new Set((l.data || []).map(r => r.title_id));
}

async function saveProgress(id, episode, position, duration) {
  if (!state.user || !(duration > 0)) return;
  const row = {
    title_id: id, episode, position_s: Math.floor(position), duration_s: Math.max(1, Math.floor(duration)),
    updated_at: new Date().toISOString(),
  };
  state.progress.set(`${id}:${episode}`, row);
  await sb.from("watch_progress").upsert({ ...row, user_id: state.user.id }).then(() => {}, () => {});
}

async function toggleList(id) {
  if (state.myList.has(id)) {
    state.myList.delete(id);
    const { error } = await sb.from("my_list").delete().eq("title_id", id).eq("user_id", state.user.id);
    if (error) { state.myList.add(id); toast("Couldn't update My List. Try again."); }
  } else {
    state.myList.add(id);
    const { error } = await sb.from("my_list").insert({ title_id: id, user_id: state.user.id });
    if (error && error.code !== "23505") { state.myList.delete(id); toast("Couldn't update My List. Try again."); }
  }
}

const pct = r => (r && r.duration_s ? r.position_s / r.duration_s : 0);
const inProgress = r => pct(r) > 0.02 && pct(r) < 0.95;

// Latest unfinished episode (or the movie) per title, newest first.
function continueWatching() {
  const best = new Map();
  for (const r of state.progress.values()) {
    if (!inProgress(r) || !state.byId.has(r.title_id)) continue;
    const cur = best.get(r.title_id);
    if (!cur || r.updated_at > cur.updated_at) best.set(r.title_id, r);
  }
  return [...best.values()].sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1));
}

// Where Play should start for a title: a show resumes its most recent episode.
function resumeFor(t) {
  if (t.kind === "movie") {
    const r = state.progress.get(`${t.id}:0`);
    return { episode: 0, resume: inProgress(r) ? r : null };
  }
  let latest = null;
  for (const e of t.episodes) {
    const r = state.progress.get(`${t.id}:${e.number}`);
    if (r && (!latest || r.updated_at > latest.updated_at)) latest = r;
  }
  if (!latest) return { episode: 1, resume: null };
  if (inProgress(latest)) return { episode: latest.episode, resume: latest };
  const next = Math.min(latest.episode + 1, t.episodes.length);
  return { episode: next, resume: null };
}

// ---------- auth screen ----------

function renderAuth(mode = "signin", message = "") {
  document.title = "Sign in — Haukley";
  const copy = {
    signin: ["Sign in to watch", "Free movies and shows. No credit card, ever.", "Sign in"],
    signup: ["Create your free account", "Just an email and a password. No credit card, ever.", "Create account"],
    forgot: ["Reset your password", "We'll email you a link to set a new one.", "Send reset link"],
    recover: ["Set a new password", "Choose a password with at least 8 characters.", "Save password"],
  }[mode];
  app.innerHTML = `
    <main class="auth">
      <div class="auth-box">
        <a class="wordmark" href="/">Haukley<span>.</span></a>
        <h1>${copy[0]}</h1>
        <p class="sub">${copy[1]}</p>
        <form id="auth-form" novalidate>
          ${mode === "recover" ? "" : `<label>Email<input type="email" name="email" autocomplete="email" required></label>`}
          ${mode === "forgot" ? "" : `<label>Password<input type="password" name="password" minlength="8" required
              autocomplete="${mode === "signin" ? "current-password" : "new-password"}"></label>`}
          <button class="btn btn-primary" type="submit">${copy[2]}</button>
          <p class="note" role="status">${esc(message)}</p>
        </form>
        <div class="links">
          ${mode === "signin" ? `<button data-mode="signup">New here? Create a free account</button><button data-mode="forgot">Forgot password?</button>` : ""}
          ${mode === "signup" || mode === "forgot" ? `<button data-mode="signin">Already have an account? Sign in</button>` : ""}
        </div>
        <p class="fine">By continuing you agree to the <a href="/terms/">Terms</a> and <a href="/privacy/">Privacy Policy</a>.</p>
      </div>
    </main>`;
  const form = $("#auth-form");
  const note = $(".note", form);
  const say = (t, cls = "") => { note.textContent = t; note.className = "note " + cls; };
  app.querySelectorAll("[data-mode]").forEach(b => b.addEventListener("click", () => renderAuth(b.dataset.mode)));
  const first = $("input", form);
  if (first && matchMedia("(pointer: fine)").matches) first.focus();

  form.addEventListener("submit", async e => {
    e.preventDefault();
    const email = (form.email?.value || "").trim();
    const password = form.password?.value || "";
    if (mode !== "recover" && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return say("Enter a valid email address.", "err");
    if (mode !== "forgot" && password.length < 8) return say("Passwords need at least 8 characters.", "err");
    const button = $("button[type=submit]", form);
    button.disabled = true;
    say("One moment…");
    try {
      let res;
      if (mode === "signin") res = await sb.auth.signInWithPassword({ email, password });
      else if (mode === "signup") res = await sb.auth.signUp({ email, password });
      else if (mode === "forgot") res = await sb.auth.resetPasswordForEmail(email, { redirectTo: location.origin + "/watch/" });
      else res = await sb.auth.updateUser({ password });
      if (res.error) throw res.error;
      if (mode === "forgot") return say("If that email has an account, a reset link is on its way.", "ok");
      if (mode === "recover") { state.recovering = false; toast("Password updated."); }
      if (mode === "signup" && !res.data.session) {
        // Only happens if email confirmation is ever turned back on.
        return say("Check your email to finish creating your account.", "ok");
      }
      await boot();
    } catch (err) {
      say(authMessage(err, mode), "err");
    } finally {
      button.disabled = false;
    }
  });
}

function authMessage(err, mode) {
  const m = String(err?.message || "");
  if (/invalid login credentials/i.test(m)) return "That email and password don't match. Try again or reset your password.";
  if (/already registered|already been registered/i.test(m)) return "There's already an account with that email. Sign in instead.";
  if (/rate limit|too many/i.test(m)) return "Too many tries. Wait a minute and try again.";
  if (/password/i.test(m) && /(weak|short|characters)/i.test(m)) return "Choose a longer password (8+ characters).";
  if (/fetch|network/i.test(m)) return "Couldn't reach the server. Check your connection.";
  return mode === "signup" ? "Couldn't create the account. Try again." : "Something went wrong. Try again.";
}

// ---------- browse ----------

const img = (t, kind) => `${ART}${encodeURIComponent(t.id)}/${kind}.jpg`;

function header(active) {
  const initial = esc((state.user?.email || "?")[0].toUpperCase());
  const links = [["#/", "Home", "home"], ["#/movies", "Movies", "movies"], ["#/shows", "Shows", "shows"], ["#/list", "My List", "list"]];
  const nav = links.map(([h, l, k]) => `<a href="${h}" class="${active === k ? "on" : ""}">${l}</a>`).join("");
  return `
    <header class="top" id="top">
      <a class="wordmark" href="#/">Haukley<span>.</span></a>
      <nav>${nav}</nav>
      <div class="spacer"></div>
      <label class="search">
        <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" stroke-width="2"/><path d="M20 20l-4-4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
        <input id="q" type="search" placeholder="Search titles, genres, people" aria-label="Search" value="${esc(active === "search" ? decodeURIComponent(location.hash.split("q=")[1] || "") : "")}">
      </label>
      <div class="account">
        <button class="avatar" id="acct" aria-haspopup="menu" aria-expanded="false" aria-label="Account">${initial}</button>
        <div class="menu" id="acct-menu" role="menu" hidden>
          <div class="who">${esc(state.user?.email)}</div>
          <a href="#/list" role="menuitem">My List</a>
          <a href="/support/" role="menuitem">Help</a>
          <button id="signout" role="menuitem">Sign out</button>
          <button id="delete-account" class="danger" role="menuitem">Delete account</button>
        </div>
      </div>
    </header>
    <div class="mobile-nav">${nav}</div>`;
}

function wireHeader() {
  const top = $("#top");
  const onScroll = () => top.classList.toggle("solid", scrollY > 40);
  onScroll();
  window.onscroll = onScroll;
  const q = $("#q");
  let t;
  q.addEventListener("input", () => {
    clearTimeout(t);
    t = setTimeout(() => {
      const v = q.value.trim();
      location.replace(v ? `#/search?q=${encodeURIComponent(v)}` : "#/");
    }, 250);
  });
  const acct = $("#acct");
  const menu = $("#acct-menu");
  acct.addEventListener("click", e => {
    e.stopPropagation();
    menu.hidden = !menu.hidden;
    acct.setAttribute("aria-expanded", String(!menu.hidden));
  });
  document.onclick = () => { menu.hidden = true; acct.setAttribute("aria-expanded", "false"); };
  $("#signout").addEventListener("click", async () => { await sb.auth.signOut(); });
  $("#delete-account").addEventListener("click", async () => {
    if (!confirm("Delete your Haukley account? Your watch history and My List are erased. This can't be undone.")) return;
    const { error } = await sb.rpc("delete_account");
    if (error) return toast("Couldn't delete the account. Email privacy@haukley.com and we'll do it.");
    await sb.auth.signOut({ scope: "local" });
    toast("Your account was deleted.");
  });
}

function tile(t, type, opts = {}) {
  const shape = type === "poster" ? "poster" : "card";
  const r = opts.progress;
  const bar = r ? `<div class="bar"><i style="width:${Math.round(pct(r) * 100)}%"></i></div>` : "";
  const cap = shape === "card" && opts.caption ? `<div class="cap">${esc(opts.caption)}</div>` : "";
  const badge = !r && t.badge && shape === "poster" ? `<span class="badge">${esc(t.badge)}</span>` : "";
  const action = opts.play ? `data-play="${esc(t.id)}" data-ep="${opts.episode || 0}"` : `data-title="${esc(t.id)}"`;
  return `<button class="tile ${shape}" ${action} aria-label="${esc(t.title)}">
    <img src="${img(t, shape)}" alt="" loading="lazy" decoding="async">${badge}${cap}${bar}</button>`;
}

function row(title, items) {
  if (!items.length) return "";
  return `<section class="row"><h2>${esc(title)}</h2><div class="strip">${items.join("")}</div></section>`;
}

function renderHome() {
  document.title = "Haukley — Watch free";
  const cat = state.catalog;
  const featured = cat.featured.map(id => state.byId.get(id)).filter(Boolean);
  state.heroId ||= (featured[Math.floor(Math.random() * featured.length)] || cat.titles[0]).id;
  const hero = state.byId.get(state.heroId);
  const { resume } = resumeFor(hero);
  const cw = continueWatching().map(r => {
    const t = state.byId.get(r.title_id);
    const left = Math.max(1, Math.round((r.duration_s - r.position_s) / 60));
    const label = t.kind === "show" ? `E${r.episode} · ${left} min left` : `${left} min left`;
    return tile(t, "card", { progress: r, caption: `${t.title} · ${label}`, play: true, episode: r.episode });
  });
  const list = [...state.myList].map(id => state.byId.get(id)).filter(Boolean).map(t => tile(t, "poster"));
  const rows = cat.rows.map(r => {
    const titles = r.ids.map(id => state.byId.get(id)).filter(Boolean);
    const items = r.type === "ranked"
      ? titles.map((t, i) => `<div class="ranked"><span class="n" aria-hidden="true">${i + 1}</span>${tile(t, "poster")}</div>`)
      : titles.map(t => tile(t, r.type === "poster" ? "poster" : "card", { caption: r.type === "card" ? t.title : "" }));
    return row(r.title, items);
  });
  app.innerHTML = `${header("home")}
    <section class="hero">
      <div class="hero-bg" style="background-image:url('${img(hero, "backdrop")}')"></div>
      <div class="hero-body">
        <h1>${esc(hero.title)}</h1>
        <div class="meta">${metaLine(hero)}</div>
        <p class="desc">${esc(hero.description)}</p>
        <div class="actions">
          <button class="btn btn-primary" data-playtitle="${esc(hero.id)}">${playIcon()} ${resume ? "Resume" : "Play"}</button>
          <button class="btn btn-ghost" data-title="${esc(hero.id)}">More info</button>
        </div>
      </div>
    </section>
    <div class="rows">
      ${row("Continue Watching", cw)}
      ${row("My List", list)}
      ${rows.join("")}
    </div>`;
  wireHeader();
}

function renderGrid(active, heading, sub, titles, emptyText) {
  document.title = `${heading} — Haukley`;
  app.innerHTML = `${header(active)}
    <main class="page">
      <h1>${esc(heading)}</h1>${sub ? `<p class="sub">${esc(sub)}</p>` : ""}
      ${titles.length ? `<div class="grid">${titles.map(t => tile(t, "poster")).join("")}</div>` : `<p class="empty">${esc(emptyText)}</p>`}
    </main>`;
  wireHeader();
}

function metaLine(t) {
  const len = t.kind === "movie" ? t.runtime : `${t.seasons} Season${t.seasons === 1 ? "" : "s"}`;
  return [t.year, `<span class="rating">${esc(t.rating)}</span>`, esc(len), esc(t.genre)].filter(Boolean).join("<span aria-hidden='true'>·</span>");
}

const playIcon = () => `<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M7 4.5v15l13-7.5z" fill="currentColor"/></svg>`;

// ---------- title modal ----------

function openTitle(id) {
  const t = state.byId.get(id);
  if (!t) return;
  const modal = $("#modal");
  const box = $(".modal-box", modal);
  const { episode, resume } = resumeFor(t);
  const inList = state.myList.has(t.id);
  const playLabel = resume ? (t.kind === "show" ? `Resume E${episode}` : "Resume") : t.kind === "show" && episode > 1 ? `Play E${episode}` : "Play";
  const eps = t.kind === "show" ? `<h3>Episodes</h3><div class="eps">${t.episodes.map(e => {
    const r = state.progress.get(`${t.id}:${e.number}`);
    return `<button class="ep" data-play="${esc(t.id)}" data-ep="${e.number}">
      <span class="num">${e.number}</span>
      <span class="thumb"><img src="${ART}${encodeURIComponent(t.id)}/ep${e.number}.jpg" alt="" loading="lazy">${r ? `<span class="bar"><i style="width:${Math.round(pct(r) * 100)}%"></i></span>` : ""}</span>
      <span><span class="name">${esc(e.name)}<span>${e.minutes} min</span></span><p>${esc(e.summary)}</p></span>
    </button>`;
  }).join("")}</div>` : "";
  const more = state.catalog.titles.filter(x => x.id !== t.id && x.kind === t.kind).slice(0, 6);
  box.innerHTML = `
    <div class="m-hero" style="background-image:url('${img(t, "backdrop")}')">
      <button class="icon-btn m-close" data-close aria-label="Close"><svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg></button>
      <div class="m-head"><h2 id="modal-title">${esc(t.title)}</h2></div>
    </div>
    <div class="m-body">
      <div class="meta">${metaLine(t)}</div>
      <div class="actions">
        <button class="btn btn-primary" data-play="${esc(t.id)}" data-ep="${t.kind === "show" ? episode : 0}">${playIcon()} ${playLabel}</button>
        <button class="btn btn-ghost" id="list-btn" aria-pressed="${inList}">${inList ? "✓ In My List" : "+ My List"}</button>
      </div>
      <p class="tagline">${esc(t.tagline)}</p>
      <p class="desc">${esc(t.description)}</p>
      <p class="credits">${esc(t.credits)}</p>
      ${eps}
      <h3>More like this</h3>
      <div class="more">${more.map(x => tile(x, "card", { caption: x.title })).join("")}</div>
    </div>`;
  modal.hidden = false;
  document.body.classList.add("locked");
  modal.scrollTop = 0;
  $("#list-btn").addEventListener("click", async e => {
    const b = e.currentTarget;
    await toggleList(t.id);
    const on = state.myList.has(t.id);
    b.textContent = on ? "✓ In My List" : "+ My List";
    b.setAttribute("aria-pressed", String(on));
  });
  $(".m-close", box).focus({ preventScroll: true });
}

function closeModal(navigate = true) {
  const modal = $("#modal");
  if (modal.hidden) return;
  modal.hidden = true;
  document.body.classList.remove("locked");
  if (!navigate || !location.hash.startsWith("#/title/")) return;
  if (state.modalPushed) history.back();
  else location.replace(state.page || "#/"); // opened from a deep link: nothing to go back to
  state.modalPushed = false;
}

// ---------- player ----------

const player = {
  el: $("#player"), video: $("#video"), adLayer: $("#ad-layer"),
  hls: null, ima: null, id: null, episode: 0, sessionId: null, saveTimer: null, idleTimer: null,
};

let imaPromise = null;
function loadIma() {
  if (window.google?.ima) return Promise.resolve(true);
  if (!imaPromise) {
    imaPromise = new Promise(res => {
      const s = document.createElement("script");
      s.src = IMA_SDK;
      s.async = true;
      s.onload = () => res(Boolean(window.google?.ima));
      s.onerror = () => res(false); // ad blocker or offline: play without ads
      document.head.appendChild(s);
      setTimeout(() => res(Boolean(window.google?.ima)), 6000);
    });
  }
  return imaPromise;
}

function logAdEvent(event) {
  const body = JSON.stringify({ title_id: player.id, episode: player.episode, platform: "web", event, session_id: player.sessionId });
  const send = () => fetch(state.ads.trackingUrl, {
    method: "POST",
    headers: { apikey: state.ads.publishableKey, "Content-Type": "application/json", Prefer: "return=minimal" },
    body, keepalive: true,
  }).then(r => { if (!r.ok) throw new Error(String(r.status)); });
  send().catch(() => new Promise(r => setTimeout(r, 3000)).then(send)).catch(() => {});
}

// Must run inside the click that started playback so browsers allow sound + ads.
function startPlayback(id, episode) {
  const t = state.byId.get(id);
  if (!t) return;
  if (t.kind === "show" && !(episode >= 1)) episode = resumeFor(t).episode;
  if (t.kind === "movie") episode = 0;
  const e = episode ? t.episodes.find(x => x.number === episode) : null;
  const src = (e || t).stream;
  const fromModal = !$("#modal").hidden && location.hash.startsWith("#/title/");
  closeModal(false);
  stopPlayback(false);
  Object.assign(player, { id, episode, sessionId: crypto.randomUUID() });
  const { video } = player;
  $("#player-title").textContent = e ? `${t.title} · E${e.number} ${e.name}` : t.title;
  $("#player-error").hidden = true;
  player.el.hidden = false;
  document.body.classList.add("locked");
  const target = `#/play/${encodeURIComponent(id)}/${episode}`;
  // From the title modal the player replaces its history entry, so Back returns to the page.
  if (fromModal) { history.replaceState(null, "", target); state.modalPushed = false; }
  else if (location.hash !== target) history.pushState(null, "", target);

  const r = state.progress.get(`${id}:${episode}`);
  const resumeAt = inProgress(r) ? r.position_s : 0;
  video.controls = true;
  if (video.canPlayType("application/vnd.apple.mpegurl")) {
    video.src = src;
  } else if (window.Hls?.isSupported()) {
    player.hls = new Hls({ startPosition: resumeAt || -1 });
    player.hls.on(Hls.Events.ERROR, (_, d) => { if (d.fatal) showPlayerError(); });
    player.hls.loadSource(src);
    player.hls.attachMedia(video);
  } else {
    return showPlayerError("This browser can't play Haukley video. Try Chrome, Safari, Edge or Firefox.");
  }
  if (resumeAt) video.addEventListener("loadedmetadata", () => { if (video.currentTime < 1) video.currentTime = resumeAt; }, { once: true });

  if (window.google?.ima) startAds(t);
  else video.play().catch(() => {});

  player.saveTimer = setInterval(() => {
    if (!video.paused && !player.ima?.adPlaying) saveProgress(id, episode, video.currentTime, video.duration);
  }, 15000);
  poke();
}

function startAds(t) {
  const { video, adLayer } = player;
  const ima = google.ima;
  const s = { adPlaying: false, contentDone: false, manager: null };
  player.ima = s;
  s.container = new ima.AdDisplayContainer(adLayer, video);
  s.container.initialize();
  s.loader = new ima.AdsLoader(s.container);
  const playContent = () => { s.contentStarted = true; adLayer.classList.remove("on"); video.controls = true; if (!s.contentDone) video.play().catch(() => {}); };
  s.loader.addEventListener(ima.AdsManagerLoadedEvent.Type.ADS_MANAGER_LOADED, ev => {
    const settings = new ima.AdsRenderingSettings();
    settings.restoreCustomPlaybackStateOnAdBreakComplete = true;
    clearTimeout(s.timeout);
    if (s.contentStarted) return; // the timeout already started the film
    const m = ev.getAdsManager(video, settings);
    s.manager = m;
    const E = ima.AdEvent.Type;
    m.addEventListener(E.CONTENT_PAUSE_REQUESTED, () => { s.adPlaying = true; video.pause(); video.controls = false; adLayer.classList.add("on"); });
    m.addEventListener(E.CONTENT_RESUME_REQUESTED, () => { s.adPlaying = false; playContent(); });
    m.addEventListener(E.STARTED, () => logAdEvent("ad_started"));
    m.addEventListener(E.COMPLETE, () => logAdEvent("ad_completed"));
    m.addEventListener(ima.AdErrorEvent.Type.AD_ERROR, () => { s.adPlaying = false; playContent(); });
    try {
      m.init(player.el.clientWidth, player.el.clientHeight, ima.ViewMode.NORMAL);
      m.start();
    } catch {
      playContent();
    }
  });
  s.loader.addEventListener(ima.AdErrorEvent.Type.AD_ERROR, playContent);
  video.addEventListener("ended", s.onEnded = () => { s.contentDone = true; s.loader.contentComplete(); });
  const req = new ima.AdsRequest();
  req.adTagUrl = state.ads.adTagTemplate
    .replace("{TITLE_ID}", encodeURIComponent(t.id))
    .replace("{KIND}", t.kind)
    .replace("{CORRELATOR}", String(Date.now()));
  req.linearAdSlotWidth = req.nonLinearAdSlotWidth = player.el.clientWidth;
  req.linearAdSlotHeight = player.el.clientHeight;
  req.nonLinearAdSlotHeight = 150;
  s.loader.requestAds(req);
  // If the ad server never answers, start the film anyway.
  s.timeout = setTimeout(() => { if (!s.manager && player.ima === s) playContent(); }, 8000);
}

function showPlayerError(text) {
  const p = $("#player-error");
  p.textContent = text || "Couldn't play this video. Check your connection, then go back and try again.";
  p.hidden = false;
}

function stopPlayback(navigate = true) {
  const { video } = player;
  if (player.id && video.duration) saveProgress(player.id, player.episode, video.currentTime, video.duration);
  clearInterval(player.saveTimer);
  if (player.ima) {
    clearTimeout(player.ima.timeout);
    try { player.ima.manager?.destroy(); player.ima.loader.destroy(); player.ima.container.destroy(); } catch {}
    video.removeEventListener("ended", player.ima.onEnded);
    player.ima = null;
  }
  player.adLayer.classList.remove("on");
  player.adLayer.innerHTML = "";
  if (player.hls) { player.hls.destroy(); player.hls = null; }
  video.pause();
  video.removeAttribute("src");
  video.load();
  const wasOpen = !player.el.hidden;
  player.el.hidden = true;
  player.id = null;
  document.body.classList.remove("locked");
  if (navigate && wasOpen && location.hash.startsWith("#/play/")) history.back();
}

function poke() {
  player.el.classList.remove("idle");
  clearTimeout(player.idleTimer);
  player.idleTimer = setTimeout(() => { if (!player.video.paused) player.el.classList.add("idle"); }, 2500);
}

player.video.addEventListener("pause", () => {
  poke();
  if (player.id && !player.ima?.adPlaying && player.video.duration) saveProgress(player.id, player.episode, player.video.currentTime, player.video.duration);
});
player.video.addEventListener("ended", () => {
  if (player.id) saveProgress(player.id, player.episode, player.video.duration, player.video.duration);
});
player.el.addEventListener("mousemove", poke);
player.el.addEventListener("touchstart", poke, { passive: true });
$("#player-back").addEventListener("click", () => stopPlayback());
window.addEventListener("resize", () => {
  const m = player.ima?.manager;
  if (m) m.resize(player.el.clientWidth, player.el.clientHeight, google.ima.ViewMode.NORMAL);
});
window.addEventListener("pagehide", () => {
  if (player.id && player.video.duration) saveProgress(player.id, player.episode, player.video.currentTime, player.video.duration);
});

// ---------- routing ----------

function route() {
  if (!state.user) return;
  const h = location.hash || "#/";
  const play = h.match(/^#\/play\/([^/]+)\/(\d+)/);
  if (play) {
    const id = decodeURIComponent(play[1]);
    if (player.id !== id) startPlayback(id, Number(play[2])); // deep link / reload: may need a tap to start
    return;
  }
  if (!player.el.hidden) stopPlayback(false);
  const title = h.match(/^#\/title\/([^/?]+)/);
  if (title) {
    if (!app.innerHTML) renderHome();
    return openTitle(decodeURIComponent(title[1]));
  }
  const modal = $("#modal");
  if (!modal.hidden) { modal.hidden = true; document.body.classList.remove("locked"); }
  const sameAsBefore = h === state.page && app.innerHTML;
  const keepY = scrollY;
  state.page = h;
  const all = state.catalog.titles;
  if (h.startsWith("#/movies")) renderGrid("movies", "Movies", "Free to watch, every one of them.", all.filter(t => t.kind === "movie"), "");
  else if (h.startsWith("#/shows")) renderGrid("shows", "Shows", "Full seasons, free.", all.filter(t => t.kind === "show"), "");
  else if (h.startsWith("#/list")) renderGrid("list", "My List", "", [...state.myList].map(id => state.byId.get(id)).filter(Boolean), "Nothing here yet. Open any title and choose + My List.");
  else if (h.startsWith("#/search")) {
    const q = decodeURIComponent(h.split("q=")[1] || "").trim().toLowerCase();
    const hits = all.filter(t => [t.title, t.genre, t.credits, t.description].join(" ").toLowerCase().includes(q));
    renderGrid("search", q ? `Results for “${q}”` : "Search", "", hits, "No matches. Try a genre like Drama or Comedy.");
    const input = $("#q");
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
  } else renderHome();
  if (sameAsBefore) scrollTo(0, keepY); // back from a title or the player: stay where you were
  else if (!h.startsWith("#/search")) scrollTo(0, 0);
}

addEventListener("hashchange", route);
addEventListener("popstate", () => { if (!location.hash.startsWith("#/play/") && !player.el.hidden) stopPlayback(false); });

// Clicks anywhere: open a title, play, or close the modal. Playback starts synchronously
// inside the click so the browser treats it as user-initiated.
document.addEventListener("click", e => {
  const el = e.target.closest("[data-play],[data-playtitle],[data-title],[data-close]");
  if (!el) return;
  if (el.hasAttribute("data-close")) return closeModal();
  if (el.dataset.title) {
    const target = `#/title/${encodeURIComponent(el.dataset.title)}`;
    if (!$("#modal").hidden) location.replace(target); // "More like this": swap, don't stack
    else { state.modalPushed = true; location.hash = target; }
    return;
  }
  if (el.dataset.playtitle) return startPlayback(el.dataset.playtitle, resumeFor(state.byId.get(el.dataset.playtitle)).episode);
  startPlayback(el.dataset.play, Number(el.dataset.ep || 0));
});
document.addEventListener("keydown", e => {
  if (e.key !== "Escape") return;
  if (!player.el.hidden) stopPlayback();
  else closeModal();
});

function toast(text) {
  const t = document.createElement("div");
  t.className = "toast";
  t.setAttribute("role", "status");
  t.textContent = text;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3500);
}

// ---------- boot ----------

async function boot() {
  const { data } = await sb.auth.getSession();
  state.user = data.session?.user || null;
  if (!state.user || state.recovering) {
    stopPlayback(false);
    return renderAuth(state.recovering ? "recover" : "signin");
  }
  if (!state.catalog) await loadCatalog();
  await loadViewerData();
  loadIma(); // warm up so the first Play click can start ads within the gesture
  app.innerHTML = "";
  route();
}

sb.auth.onAuthStateChange((event, session) => {
  if (event === "PASSWORD_RECOVERY") { state.recovering = true; return renderAuth("recover"); }
  if (event === "SIGNED_OUT") {
    state.user = null;
    state.progress.clear();
    state.myList.clear();
    stopPlayback(false);
    $("#modal").hidden = true;
    document.body.classList.remove("locked");
    history.replaceState(null, "", "/watch/");
    renderAuth("signin");
  } else if (session?.user && state.user && session.user.id !== state.user.id) {
    boot();
  }
});

boot().catch(() => {
  app.innerHTML = `<main class="auth"><div class="auth-box"><a class="wordmark" href="/">Haukley<span>.</span></a>
    <h1>Couldn't load Haukley</h1><p class="sub">Check your connection and reload the page.</p></div></main>`;
});
