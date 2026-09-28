// Haukley web player. Signed-in viewers pick a profile, browse the same catalog as the TV and
// iPhone apps (built by scripts/make_web.py), and play HLS with Google IMA ads. Profiles,
// Continue Watching and My List live in Supabase (RLS: each account sees only its own rows).
"use strict";

const SUPABASE_URL = "https://axgxpwgbpgcqjxoqwtnv.supabase.co";
// Publishable key: public by design; every table it can reach is guarded by RLS.
const SUPABASE_KEY = "sb_publishable_9VpZfDWrMK3orLITxhWZJw_kbAFdw90";
const IMA_SDK = "https://imasdk.googleapis.com/js/sdkloader/ima3.js";
const ART = "catalog/";
const KIDS_RATINGS = new Set(["G", "PG", "TV-Y", "TV-Y7", "TV-G", "TV-PG"]);
const MAX_PROFILES = 5;
const hoverable = matchMedia("(hover: hover) and (pointer: fine)");

const sb = supabase.createClient(SUPABASE_URL, SUPABASE_KEY, {
  auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true, flowType: "pkce" },
});

const $ = (sel, root = document) => root.querySelector(sel);
const app = $("#app");
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const session = {
  get(k) { try { return sessionStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { v == null ? sessionStorage.removeItem(k) : sessionStorage.setItem(k, v); } catch {} },
};

const state = {
  user: null,
  profiles: [],
  profile: null,
  catalog: null,
  byId: new Map(),
  rank: new Map(), // id -> { n, label } from the catalog's Top 10 rows
  progress: new Map(), // "id:episode" -> { title_id, episode, position_s, duration_s, updated_at }
  myList: new Set(),
  ads: null,
  recovering: false,
  heroIds: {},
  page: null, // hash of the page under the modal/player, to restore scroll when coming back
  modalPushed: false,
};

// ---------- icons & avatars ----------

const ICON = {
  play: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3.5v17l14.5-8.5z" fill="currentColor"/></svg>`,
  info: `<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 11v6M12 7.2v.1" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>`,
  plus: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v16M4 12h16" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>`,
  check: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4.5 12.5l5 5 10-11" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  down: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 9l7 7 7-7" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  caret: `<svg class="caret" viewBox="0 0 10 10" aria-hidden="true"><path d="M1 3l4 4 4-4z" fill="currentColor"/></svg>`,
  search: `<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="7" fill="none" stroke="currentColor" stroke-width="2.2"/><path d="M16 16l5 5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>`,
  close: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>`,
  pencil: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20h4L19 9l-4-4L4 16z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>`,
  left: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 4l-8 8 8 8" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  right: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 4l8 8-8 8" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
  user: `<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="4" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>`,
  help: `<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.7M12 17v.1" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>`,
};

const AVATAR_COLORS = [
  ["#8b6cff", "#4b2fd1"], ["#ff7eb6", "#c2185b"], ["#35d0ba", "#0f766e"], ["#ffb547", "#e8590c"],
  ["#5ab0ff", "#1d4ed8"], ["#b4e36b", "#3f8f1f"], ["#ff6b6b", "#b91c1c"], ["#c792ea", "#7b1fa2"],
  ["#4dd4ff", "#0e7490"], ["#ffd54f", "#b8860b"], ["#a0aec0", "#475569"], ["#f472b6", "#7e22ce"],
];
// Simple generated faces: gradient square, eyes and a smile that vary by index.
function avatarSvg(i, kids = false) {
  const [a, b] = AVATAR_COLORS[i % AVATAR_COLORS.length];
  const id = `g${i}${kids ? "k" : ""}`;
  const eye = i % 3 === 0 ? `<circle cx="35" cy="42" r="6"/><circle cx="65" cy="42" r="6"/>`
    : i % 3 === 1 ? `<rect x="29" y="37" width="12" height="10" rx="5"/><rect x="59" y="37" width="12" height="10" rx="5"/>`
    : `<path d="M28 44q7-9 14 0M58 44q7-9 14 0" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round"/>`;
  const mouth = i % 2 ? `<path d="M32 62q18 18 36 0" fill="none" stroke="#fff" stroke-width="5.5" stroke-linecap="round"/>`
    : `<path d="M34 60q16 14 32 0z" fill="#fff"/>`;
  const label = kids ? `<text x="50" y="92" text-anchor="middle" font-family="Inter, sans-serif" font-size="15" font-weight="800" fill="#fff">kids</text>` : "";
  return `<svg viewBox="0 0 100 100" aria-hidden="true"><defs><linearGradient id="${id}" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="${a}"/><stop offset="1" stop-color="${b}"/></linearGradient></defs>
    <rect width="100" height="100" fill="url(#${id})"/><g fill="#fff">${eye}</g>${mouth}${label}</svg>`;
}
const avatarOf = p => `<span class="avatar">${avatarSvg(p.avatar, p.is_kids)}</span>`;

// ---------- data ----------

async function loadCatalog() {
  const [cat, ads] = await Promise.all([
    fetch(ART + "catalog.json").then(r => r.json()),
    fetch(ART + "ads.json").then(r => r.json()),
  ]);
  state.catalog = cat;
  state.ads = ads;
  state.byId = new Map(cat.titles.map(t => [t.id, t]));
  for (const r of cat.rows.filter(r => r.type === "ranked")) {
    r.ids.forEach((id, i) => { if (!state.rank.has(id)) state.rank.set(id, { n: i + 1, label: r.title }); });
  }
}

async function loadProfiles() {
  const { data, error } = await sb.from("profiles").select("id,name,avatar,is_kids,created_at").order("created_at");
  if (error) throw error;
  state.profiles = data;
  if (!data.length) {
    const local = (state.user.email || "You").split("@")[0].split("+")[0].replace(/[._+-]+/g, " ").trim();
    const name = (local.charAt(0).toUpperCase() + local.slice(1)).slice(0, 30) || "You";
    const ins = await sb.from("profiles").insert({ name, avatar: 0, user_id: state.user.id }).select("id,name,avatar,is_kids,created_at").single();
    if (ins.error) throw ins.error;
    state.profiles = [ins.data];
  }
}

async function loadViewerData() {
  const pid = state.profile.id;
  const [p, l] = await Promise.all([
    sb.from("watch_progress").select("title_id,episode,position_s,duration_s,updated_at").eq("profile_id", pid),
    sb.from("my_list").select("title_id,added_at").eq("profile_id", pid).order("added_at", { ascending: false }),
  ]);
  state.progress = new Map((p.data || []).map(r => [`${r.title_id}:${r.episode}`, r]));
  state.myList = new Set((l.data || []).map(r => r.title_id));
}

async function saveProgress(id, episode, position, duration) {
  if (!state.user || !state.profile || !(duration > 0)) return;
  const row = {
    title_id: id, episode, position_s: Math.floor(position), duration_s: Math.max(1, Math.floor(duration)),
    updated_at: new Date().toISOString(),
  };
  state.progress.set(`${id}:${episode}`, row);
  await sb.from("watch_progress").upsert({ ...row, user_id: state.user.id, profile_id: state.profile.id }).then(() => {}, () => {});
}

async function toggleList(id) {
  const pid = state.profile.id;
  if (state.myList.has(id)) {
    state.myList.delete(id);
    const { error } = await sb.from("my_list").delete().eq("profile_id", pid).eq("title_id", id);
    if (error) { state.myList.add(id); return toast("Couldn't update My List. Try again."); }
    toast("Removed from My List");
  } else {
    state.myList.add(id);
    const { error } = await sb.from("my_list").insert({ title_id: id, user_id: state.user.id, profile_id: pid });
    if (error && error.code !== "23505") { state.myList.delete(id); return toast("Couldn't update My List. Try again."); }
    toast("Added to My List");
  }
}

const visible = t => t && (!state.profile?.is_kids || t.kids || KIDS_RATINGS.has(t.rating));
const titles = () => state.catalog.titles.filter(visible);
const pct = r => (r && r.duration_s ? r.position_s / r.duration_s : 0);
const inProgress = r => pct(r) > 0.02 && pct(r) < 0.95;

// Latest unfinished episode (or the movie) per title, newest first.
function continueWatching(kind) {
  const best = new Map();
  for (const r of state.progress.values()) {
    const t = state.byId.get(r.title_id);
    if (!inProgress(r) || !visible(t) || (kind && t.kind !== kind)) continue;
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
  return { episode: Math.min(latest.episode + 1, t.episodes.length), resume: null };
}

// ---------- auth screen ----------

// Sign-in providers the auth server has switched on (public endpoint). Google's button only
// renders once the provider is enabled in Supabase, so it can't appear half-configured.
let providersPromise = null;
const providers = () => (providersPromise ||= fetch(`${SUPABASE_URL}/auth/v1/settings`, { headers: { apikey: SUPABASE_KEY } })
  .then(r => r.json()).then(s => s.external || {}).catch(() => ({})));

const COMMON_PASSWORDS = new Set(["password", "password1", "password123", "12345678", "123456789", "1234567890", "qwerty123",
  "qwertyuiop", "iloveyou", "11111111", "00000000", "abc12345", "abcd1234", "letmein1", "welcome1", "football", "baseball",
  "sunshine", "princess", "dragon12", "monkey12", "passw0rd", "p@ssw0rd", "trustno1", "starwars", "whatever", "superman",
  "1q2w3e4r", "zaq12wsx", "haukley1", "haukley123", "netflix1"]);

// 0 too short, 1 weak, 2 fair, 3 good, 4 strong. Sign-up needs 2+.
function passwordStrength(pw, email = "") {
  const lower = pw.toLowerCase();
  const local = email.split("@")[0].toLowerCase();
  const kinds = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter(r => r.test(pw)).length;
  const common = COMMON_PASSWORDS.has(lower) || /^(.)\1+$/.test(pw) || /^(0123|1234|abcd|qwer|asdf|pass)/i.test(pw);
  const personal = local.length >= 3 && lower.includes(local);
  const checks = { length: pw.length >= 8, mix: kinds >= 2, unique: pw.length > 0 && !common && !personal };
  let score = 0;
  if (checks.length) {
    score = 1 + (pw.length >= 12) + (pw.length >= 16) + (kinds >= 2) + (kinds >= 3);
    if (!checks.unique) score = 1;
    else if (!checks.mix) score = Math.min(score, pw.length >= 14 ? 2 : 1);
    score = Math.min(4, score);
  }
  return { score, checks, label: ["Too short", "Weak", "Fair", "Good", "Strong"][score] };
}

const GOOGLE_G = `<svg viewBox="0 0 48 48" width="20" height="20" aria-hidden="true"><path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.5 30.3 0 24 0 14.6 0 6.6 5.4 2.7 13.3l7.9 6.1C12.5 13.6 17.8 9.5 24 9.5z"/><path fill="#4285F4" d="M46.1 24.5c0-1.6-.1-3.1-.4-4.5H24v8.5h12.4c-.5 2.9-2.1 5.3-4.6 6.9l7.4 5.7c4.3-4 6.9-9.9 6.9-16.6z"/><path fill="#FBBC05" d="M10.6 28.6c-.5-1.4-.8-3-.8-4.6s.3-3.2.8-4.6l-7.9-6.1C1 16.6 0 20.2 0 24s1 7.4 2.7 10.7l7.9-6.1z"/><path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.4-5.7c-2.1 1.4-4.8 2.3-8.5 2.3-6.2 0-11.5-4.1-13.4-9.9l-7.9 6.1C6.6 42.6 14.6 48 24 48z"/></svg>`;
const EYE = `<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>`;

function pwField(name, label, autocomplete) {
  return `<label>${label}<span class="pw"><input type="password" name="${name}" minlength="8" required autocomplete="${autocomplete}">
    <button type="button" class="pw-eye" aria-label="Show password" aria-pressed="false">${EYE}</button></span></label>`;
}

function renderAuth(mode = "signin", message = "") {
  document.title = "Sign in — Haukley";
  const copy = {
    signin: ["Sign in to watch", "Free movies and shows. No credit card, ever.", "Sign in"],
    signup: ["Create your free account", "Free forever. No credit card, ever.", "Create account"],
    forgot: ["Reset your password", "We'll email you a link to set a new one.", "Send reset link"],
    recover: ["Set a new password", "Choose a strong password you don't use anywhere else.", "Save password"],
  }[mode];
  const newPw = mode === "signup" || mode === "recover";
  const oauth = mode === "signin" || mode === "signup";
  app.innerHTML = `
    <main class="auth">
      <div class="auth-box">
        <a class="wordmark" href="/">Haukley<span>.</span></a>
        <h1>${copy[0]}</h1>
        <p class="sub">${copy[1]}</p>
        ${oauth ? `<div class="oauth" id="oauth" hidden>
          <button type="button" class="btn btn-google" id="google">${GOOGLE_G} ${mode === "signup" ? "Sign up" : "Continue"} with Google</button>
          <div class="or"><span>or</span></div></div>` : ""}
        <form id="auth-form" novalidate>
          ${mode === "recover" ? "" : `<label>Email<input type="email" name="email" autocomplete="email" required></label>`}
          ${mode === "forgot" ? "" : pwField("password", newPw ? "Password" : "Password", mode === "signin" ? "current-password" : "new-password")}
          ${newPw ? `
            <div class="meter" id="meter" aria-live="polite" hidden>
              <div class="bars" data-score="0"><i></i><i></i><i></i><i></i></div>
              <span class="meter-label"></span>
            </div>
            <ul class="reqs" id="reqs">
              <li data-req="length">At least 8 characters</li>
              <li data-req="mix">A mix of letters, numbers or symbols</li>
              <li data-req="unique">Not a common password or your email</li>
            </ul>
            ${pwField("confirm", "Confirm password", "new-password")}
            <p class="match" id="match" aria-live="polite"></p>` : ""}
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
  app.querySelectorAll(".pw-eye").forEach(b => b.addEventListener("click", () => {
    const input = b.previousElementSibling;
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    b.setAttribute("aria-pressed", String(show));
    b.setAttribute("aria-label", show ? "Hide password" : "Show password");
  }));
  const first = $("input", form);
  if (first && hoverable.matches) first.focus();

  if (oauth) {
    providers().then(p => { if (p.google && $("#oauth")) $("#oauth").hidden = false; });
    $("#google").addEventListener("click", async () => {
      say("Opening Google…");
      const { error } = await sb.auth.signInWithOAuth({ provider: "google", options: { redirectTo: location.origin + "/watch/" } });
      if (error) say("Couldn't open Google sign-in. Try again or use email.", "err");
    });
  }

  // Live password feedback: strength meter, requirement checklist, and confirm match.
  const pw = form.password;
  const confirmInput = form.confirm;
  let confirmTouched = false;
  const check = () => {
    if (!newPw) return true;
    const s = passwordStrength(pw.value, form.email?.value || state.user?.email || "");
    $("#meter").hidden = !pw.value;
    $("#meter .bars").dataset.score = String(s.score);
    $("#meter .meter-label").textContent = pw.value ? s.label : "";
    for (const [k, ok] of Object.entries(s.checks)) {
      const li = $(`[data-req="${k}"]`);
      li.classList.toggle("ok", ok);
      li.classList.toggle("bad", !ok && pw.value.length > 0 && (k !== "length" || pw.value.length >= 1));
    }
    const m = $("#match");
    const matches = confirmInput.value.length > 0 && confirmInput.value === pw.value;
    if (!confirmInput.value) { m.textContent = ""; m.className = "match"; }
    else if (matches) { m.textContent = "✓ Passwords match"; m.className = "match ok"; }
    else if (confirmTouched || confirmInput.value.length >= pw.value.length) { m.textContent = "Passwords don't match"; m.className = "match err"; }
    else { m.textContent = ""; m.className = "match"; }
    return s.score >= 2 && matches;
  };
  if (newPw) {
    pw.addEventListener("input", check);
    form.email?.addEventListener("input", check);
    confirmInput.addEventListener("input", check);
    confirmInput.addEventListener("blur", () => { confirmTouched = true; check(); });
  }

  form.addEventListener("submit", async e => {
    e.preventDefault();
    const email = (form.email?.value || "").trim();
    const password = pw?.value || "";
    if (mode !== "recover" && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return say("Enter a valid email address.", "err");
    if (mode === "signin" && !password) return say("Enter your password.", "err");
    if (newPw) {
      confirmTouched = true;
      const s = passwordStrength(password, email || state.user?.email || "");
      check();
      if (s.score < 2) return say(s.score === 0 ? "Passwords need at least 8 characters." : "That password is too easy to guess. Make it longer or mix in numbers and symbols.", "err");
      if (confirmInput.value !== password) return say("The two passwords don't match.", "err");
    }
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
      if (mode === "signup" && !res.data.session) return say("Check your email to finish creating your account.", "ok");
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

// ---------- profiles ----------

function renderWho(manage = false) {
  document.title = "Who's watching? — Haukley";
  hidePreview();
  window.onscroll = null;
  const items = state.profiles.map(p => `
    <button class="who-item" data-profile="${esc(p.id)}">
      <span class="avatar avatar-lg">${avatarSvg(p.avatar, p.is_kids)}${manage ? `<span class="edit-mark">${ICON.pencil}</span>` : ""}</span>
      <span class="nm">${esc(p.name)}</span>
    </button>`).join("");
  const add = state.profiles.length < MAX_PROFILES ? `
    <button class="who-item" data-add-profile>
      <span class="avatar avatar-lg avatar-add">${ICON.plus}</span><span class="nm">Add Profile</span>
    </button>` : "";
  app.innerHTML = `
    <div class="who-page">
      <span class="wordmark">Haukley<span>.</span></span>
      <main class="who">
        <h1>${manage ? "Manage Profiles" : "Who's watching?"}</h1>
        <div class="who-grid">${items}${add}</div>
        ${manage ? `<button class="btn btn-primary done-btn" data-done>Done</button>`
                 : `<button class="manage-btn" data-manage>${ICON.pencil} Manage Profiles</button>`}
      </main>
    </div>`;
  app.querySelectorAll("[data-profile]").forEach(b => b.addEventListener("click", () => {
    const p = state.profiles.find(x => x.id === b.dataset.profile);
    manage ? renderProfileForm(p) : chooseProfile(p);
  }));
  $("[data-add-profile]")?.addEventListener("click", () => renderProfileForm(null));
  $("[data-manage]")?.addEventListener("click", () => renderWho(true));
  $("[data-done]")?.addEventListener("click", () => renderWho(false));
}

function renderProfileForm(p) {
  const editing = Boolean(p);
  let avatar = p ? p.avatar : state.profiles.length % AVATAR_COLORS.length;
  let kids = p ? p.is_kids : false;
  const paint = () => {
    $("#pf-avatar").innerHTML = avatarSvg(avatar, kids);
    app.querySelectorAll("[data-av]").forEach(b => b.setAttribute("aria-pressed", String(Number(b.dataset.av) === avatar)));
  };
  app.innerHTML = `
    <div class="who-page">
      <span class="wordmark">Haukley<span>.</span></span>
      <main class="who">
        <h1>${editing ? "Edit Profile" : "Add Profile"}</h1>
        <form class="profile-form" id="pf" novalidate>
          <div class="row-top">
            <span class="avatar" id="pf-avatar"></span>
            <label class="field">Name<input name="name" maxlength="30" required value="${esc(p?.name || "")}" autocomplete="off"></label>
          </div>
          <div class="avatar-pick" role="group" aria-label="Choose an icon">
            ${AVATAR_COLORS.map((_, i) => `<button type="button" data-av="${i}" aria-label="Icon ${i + 1}">${avatarSvg(i)}</button>`).join("")}
          </div>
          <label class="check"><input type="checkbox" name="kids" ${kids ? "checked" : ""}> Kids profile — only shows family-friendly titles</label>
          <p class="note" role="status"></p>
          <div class="form-actions">
            <button class="btn btn-primary" type="submit">Save</button>
            <button class="btn btn-ghost" type="button" data-cancel>Cancel</button>
            ${editing && state.profiles.length > 1 ? `<button class="danger" type="button" data-delete>Delete profile</button>` : ""}
          </div>
        </form>
      </main>
    </div>`;
  paint();
  const form = $("#pf");
  const note = $(".note", form);
  app.querySelectorAll("[data-av]").forEach(b => b.addEventListener("click", () => { avatar = Number(b.dataset.av); paint(); }));
  form.kids.addEventListener("change", () => { kids = form.kids.checked; paint(); });
  $("[data-cancel]").addEventListener("click", () => renderWho(true));
  $("[data-delete]")?.addEventListener("click", async () => {
    if (!confirm(`Delete ${p.name}'s profile? Its watch history and My List are erased.`)) return;
    const { error } = await sb.from("profiles").delete().eq("id", p.id);
    if (error) { note.textContent = "Couldn't delete the profile. Try again."; note.className = "note err"; return; }
    state.profiles = state.profiles.filter(x => x.id !== p.id);
    if (state.profile?.id === p.id) { state.profile = null; session.set("hk-profile", null); }
    renderWho(true);
  });
  if (hoverable.matches) form.name.focus();
  form.addEventListener("submit", async e => {
    e.preventDefault();
    const name = form.name.value.trim();
    if (!name) { note.textContent = "Give the profile a name."; note.className = "note err"; return; }
    const row = { name, avatar, is_kids: kids };
    const q = editing
      ? sb.from("profiles").update(row).eq("id", p.id).select("id,name,avatar,is_kids,created_at").single()
      : sb.from("profiles").insert({ ...row, user_id: state.user.id }).select("id,name,avatar,is_kids,created_at").single();
    const { data, error } = await q;
    if (error) {
      note.textContent = /limit/i.test(error.message) ? `An account can have up to ${MAX_PROFILES} profiles.` : "Couldn't save. Try again.";
      note.className = "note err";
      return;
    }
    state.profiles = editing ? state.profiles.map(x => (x.id === data.id ? data : x)) : [...state.profiles, data];
    if (state.profile?.id === data.id) state.profile = data;
    renderWho(true);
  });
}

async function chooseProfile(p) {
  state.profile = p;
  session.set("hk-profile", p.id);
  state.heroIds = {};
  renderSkeleton();
  await loadViewerData();
  loadIma(); // warm up so the first Play click can start ads within the gesture
  state.page = null;
  if (!location.hash || location.hash === "#/") route();
  else location.hash = "#/";
}

// ---------- browse ----------

const img = (t, kind) => `${ART}${encodeURIComponent(t.id)}/${kind}.jpg`;
const artTitle = (t, tag = "h1", id = "") =>
  `<${tag} class="art-title f-${esc(t.font || "Montserrat")}" style="font-family:'${esc(t.font || "Montserrat")}',Inter,sans-serif"${id ? ` id="${id}"` : ""}>${esc(t.title)}</${tag}>`;

function header(active) {
  const p = state.profile;
  const links = [["#/", "Home", "home"], ["#/shows", "Shows", "shows"], ["#/movies", "Movies", "movies"],
    ["#/new", "New & Popular", "new"], ["#/list", "My List", "list"]];
  const nav = links.map(([h, l, k]) => `<a href="${h}" class="${active === k ? "on" : ""}">${l}</a>`).join("");
  const kidsProfile = state.profiles.find(x => x.is_kids);
  const kids = p.is_kids
    ? `<button class="kids-link" data-exit-kids><span>Exit Kids</span></button>`
    : kidsProfile ? `<button class="kids-link" data-switch="${esc(kidsProfile.id)}">${avatarOf(kidsProfile)}<span>Kids</span></button>` : "";
  const others = state.profiles.filter(x => x.id !== p.id)
    .map(x => `<button class="mi" data-switch="${esc(x.id)}">${avatarOf(x)}${esc(x.name)}</button>`).join("");
  const q = active === "search" ? decodeURIComponent(location.hash.split("q=")[1] || "") : "";
  return `
    <header class="top" id="top">
      <a class="wordmark" href="#/">Haukley<span>.</span></a>
      <nav aria-label="Browse">${nav}</nav>
      <div class="spacer"></div>
      <label class="search${q ? " open" : ""}" id="search">
        <button type="button" id="search-btn" aria-label="Search">${ICON.search}</button>
        <input id="q" type="search" placeholder="Titles, people, genres" aria-label="Search" value="${esc(q)}">
      </label>
      ${kids}
      <div class="account">
        <button class="acct-btn" id="acct" aria-haspopup="menu" aria-expanded="false" aria-label="Profile and account">${avatarOf(p)}${ICON.caret}</button>
        <div class="menu" id="acct-menu" role="menu" hidden>
          ${others}
          <button class="mi" data-manage-profiles>${ICON.pencil.replace("<svg", '<svg class="ic"')}Manage Profiles</button>
          <button class="mi" data-who>${ICON.user}Switch Profile</button>
          <a class="mi" href="/support/">${ICON.help}Help Center</a>
          <hr>
          <div class="who-line">${esc(state.user?.email)}</div>
          <button class="mi" id="signout">Sign out of Haukley</button>
          <button class="mi danger" id="delete-account">Delete account</button>
        </div>
      </div>
    </header>
    <div class="mobile-nav">${nav}</div>`;
}

function wireHeader() {
  const top = $("#top");
  const onScroll = () => { top.classList.toggle("solid", scrollY > 10); hidePreview(); };
  onScroll();
  window.onscroll = onScroll;
  const box = $("#search");
  const q = $("#q");
  $("#search-btn").addEventListener("click", () => { box.classList.add("open"); q.focus(); });
  q.addEventListener("blur", () => { if (!q.value) box.classList.remove("open"); });
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
  document.onclick = e => {
    if (!e.target.closest("#acct-menu")) { menu.hidden = true; acct.setAttribute("aria-expanded", "false"); }
    if (!e.target.closest(".genres")) $(".genres .menu")?.setAttribute("hidden", "");
  };
  app.querySelectorAll("[data-switch]").forEach(b => b.addEventListener("click", () =>
    chooseProfile(state.profiles.find(x => x.id === b.dataset.switch))));
  $("[data-exit-kids]")?.addEventListener("click", () => { session.set("hk-profile", null); renderWho(false); });
  $("[data-manage-profiles]").addEventListener("click", () => renderWho(true));
  $("[data-who]").addEventListener("click", () => renderWho(false));
  $("#signout").addEventListener("click", async () => { await sb.auth.signOut(); });
  $("#delete-account").addEventListener("click", async () => {
    if (!confirm("Delete your Haukley account? All profiles, watch history and My List are erased. This can't be undone.")) return;
    const { error } = await sb.rpc("delete_account");
    if (error) return toast("Couldn't delete the account. Email privacy@haukley.com and we'll do it.");
    await sb.auth.signOut({ scope: "local" });
    toast("Your account was deleted.");
  });
  wireRows();
}

function flagFor(t) {
  const r = continueWatching().find(x => x.title_id === t.id);
  if (r) return "";
  return t.badge ? `<span class="flag">${esc(t.badge)}</span>` : "";
}
const top10Badge = t => (state.rank.has(t.id) ? `<span class="top10" aria-label="Top 10">TOP<b>10</b></span>` : "");

function card(t, opts = {}) {
  const r = opts.progress;
  const action = opts.play ? `data-play="${esc(t.id)}" data-ep="${opts.episode || 0}"` : `data-title="${esc(t.id)}"`;
  return `<button class="tile${r ? " cw" : ""}" ${action} data-tid="${esc(t.id)}" aria-label="${esc(t.title)}">
    <div class="pic"><img src="${img(t, "card")}" alt="" loading="lazy" decoding="async">${r ? "" : top10Badge(t) + flagFor(t)}</div>
    ${r ? `<div class="bar"><i style="width:${Math.round(pct(r) * 100)}%"></i></div>` : ""}</button>`;
}

function rankedCard(t, n) {
  return `<div class="ranked"><span class="n" aria-hidden="true">${n}</span>
    <button class="tile" data-title="${esc(t.id)}" data-tid="${esc(t.id)}" aria-label="#${n} ${esc(t.title)}">
      <div class="pic"><img src="${img(t, "poster")}" alt="" loading="lazy" decoding="async">${flagFor(t)}</div></button></div>`;
}

function row(title, items) {
  if (!items.length) return "";
  return `<section class="row"><h2>${esc(title)}</h2><div class="strip-wrap">
    <button class="pager l" aria-label="Scroll left" disabled>${ICON.left}</button>
    <div class="strip">${items.join("")}</div>
    <button class="pager r" aria-label="Scroll right">${ICON.right}</button></div></section>`;
}

function wireRows() {
  app.querySelectorAll(".strip-wrap").forEach(w => {
    const strip = $(".strip", w);
    const l = $(".pager.l", w);
    const r = $(".pager.r", w);
    const upd = () => {
      l.disabled = strip.scrollLeft < 4;
      r.disabled = strip.scrollLeft + strip.clientWidth >= strip.scrollWidth - 4;
    };
    upd();
    strip.addEventListener("scroll", () => { upd(); hidePreview(); }, { passive: true });
    const page = dir => strip.scrollBy({ left: dir * (strip.clientWidth - 2 * parseFloat(getComputedStyle(strip).paddingLeft)), behavior: "smooth" });
    l.addEventListener("click", () => page(-1));
    r.addEventListener("click", () => page(1));
  });
}

function metaLine(t, withKind = false) {
  const len = t.kind === "movie" ? t.runtime : `${t.seasons} Season${t.seasons === 1 ? "" : "s"}`;
  const parts = [withKind ? (t.kind === "movie" ? "Movie" : "Series") : null, withKind ? esc(t.genre) : null, t.year, esc(len),
    `<span class="rating">${esc(t.rating)}</span>`, t.silent ? "Silent" : null].filter(Boolean);
  return parts.join(`<span class="dot" aria-hidden="true">•</span>`);
}

function chipsFor(t) {
  const c = [];
  if (t.badge) c.push(`<span class="chip"><i>NEW</i>${esc(t.badge)}</span>`);
  const rk = state.rank.get(t.id);
  if (rk) c.push(`<span class="chip"><i>TOP 10</i>#${rk.n} in ${esc(rk.label)}</span>`);
  return c.join("");
}

function hero(t) {
  const { resume, episode } = resumeFor(t);
  const label = resume ? (t.kind === "show" ? `Resume E${episode}` : "Resume") : "Play";
  return `
    <div class="hero-wrap"><section class="hero">
      <div class="hero-bg" style="background-image:url('${img(t, "backdrop")}')"></div>
      <div class="hero-body">
        ${artTitle(t)}
        <div class="meta">${metaLine(t, true)}</div>
        <p class="desc">${esc(t.description)}</p>
        <div class="actions">
          <button class="btn btn-primary" data-playtitle="${esc(t.id)}">${ICON.play} ${label}</button>
          <button class="btn btn-ghost" data-title="${esc(t.id)}">${ICON.info} More Info</button>
        </div>
      </div>
      <div class="chips">${chipsFor(t)}</div>
    </section></div>`;
}

function pickHero(key, pool) {
  if (!pool.length) return null;
  if (!state.heroIds[key] || !pool.some(t => t.id === state.heroIds[key])) {
    state.heroIds[key] = pool[Math.floor(Math.random() * pool.length)].id;
  }
  return state.byId.get(state.heroIds[key]);
}

function cwRow(kind) {
  const items = continueWatching(kind).map(r => card(state.byId.get(r.title_id), { progress: r, play: true, episode: r.episode }));
  return row(`Continue Watching for ${state.profile.name}`, items);
}

function catalogRows(filter = () => true) {
  return state.catalog.rows.map(r => {
    const ts = r.ids.map(id => state.byId.get(id)).filter(t => visible(t) && filter(t));
    if (r.type === "ranked") return row(r.title,
      ts.map((t, i) => rankedCard(t, i + 1)));
    return row(r.title, ts.map(t => card(t)));
  });
}

function genreRows(pool) {
  const by = new Map();
  for (const t of pool) {
    const g = t.genre.split(" ").pop(); // "Crime Drama" -> "Drama"
    by.set(g, [...(by.get(g) || []), t]);
  }
  return [...by.entries()].filter(([, ts]) => ts.length > 1).map(([g, ts]) => row(`${g}`, ts.map(t => card(t))));
}

function renderHome() {
  document.title = "Home — Haukley";
  const pool = state.catalog.featured.map(id => state.byId.get(id)).filter(visible);
  const h = pickHero("home", pool.length ? pool : titles());
  const list = [...state.myList].map(id => state.byId.get(id)).filter(visible).map(t => card(t));
  app.innerHTML = `${header("home")}
    ${h ? hero(h) : ""}
    <div class="rows">
      ${cwRow()}
      ${row("My List", list)}
      ${catalogRows().join("")}
      ${state.profile.is_kids ? genreRows(titles()).join("") : ""}
    </div>`;
  wireHeader();
}

function renderKind(kind, genre) {
  const label = kind === "movie" ? "Movies" : "Shows";
  document.title = `${label} — Haukley`;
  const pool = titles().filter(t => t.kind === kind);
  const genres = [...new Set(pool.map(t => t.genre))].sort();
  const head = `<div class="page-head"><h1>${genre ? `${label} › ${esc(genre)}` : label}</h1>
    <div class="genres"><button type="button" id="genres-btn" aria-haspopup="menu">${genre ? "All genres" : "Genres"} ${ICON.caret}</button>
      <div class="menu" role="menu" hidden>
        ${genre ? `<button data-genre="">All ${label}</button>` : ""}
        ${genres.map(g => `<button data-genre="${esc(g)}">${esc(g)}</button>`).join("")}
      </div></div></div>`;
  if (!pool.length) {
    app.innerHTML = `${header(kind === "movie" ? "movies" : "shows")}
      <main class="page"><h1>${label}</h1><p class="empty">${label} are on the way. In the meantime, every film on Haukley is free to watch now.</p>
      <p style="margin-top:20px"><a class="btn btn-primary" href="#/movies">Browse movies</a></p></main>`;
    return wireHeader();
  }
  if (genre) {
    const hits = pool.filter(t => t.genre === genre);
    app.innerHTML = `${header(kind === "movie" ? "movies" : "shows")}${head}
      <main class="page" style="padding-top:8px">${hits.length ? `<div class="grid">${hits.map(t => card(t)).join("")}</div>` : `<p class="empty">Nothing in ${esc(genre)} yet.</p>`}</main>`;
  } else {
    const h = pickHero(kind, pool.filter(t => state.catalog.featured.includes(t.id)).concat(pool).slice(0, 6));
    app.innerHTML = `${header(kind === "movie" ? "movies" : "shows")}${head}
      ${h ? hero(h) : ""}
      <div class="rows">
        ${cwRow(kind)}
        ${catalogRows(t => t.kind === kind).join("")}
        ${genreRows(pool).join("")}
        ${row(`All ${label}`, pool.map(t => card(t)))}
      </div>`;
  }
  wireHeader();
  const btn = $("#genres-btn");
  const menu = $(".genres .menu");
  btn.addEventListener("click", e => { e.stopPropagation(); menu.hidden = !menu.hidden; });
  app.querySelectorAll("[data-genre]").forEach(b => b.addEventListener("click", () => {
    const base = kind === "movie" ? "#/movies" : "#/shows";
    location.hash = b.dataset.genre ? `${base}?g=${encodeURIComponent(b.dataset.genre)}` : base;
  }));
}

function renderNew() {
  document.title = "New & Popular — Haukley";
  const pool = titles();
  const newest = [...pool].sort((a, b) => b.year - a.year || a.title.localeCompare(b.title));
  const ranked = state.catalog.rows.filter(r => r.type === "ranked");
  app.innerHTML = `${header("new")}
    <div class="page-head"><h1>New &amp; Popular</h1></div>
    <div class="rows">
      ${row("Just Added to Haukley", newest.map(t => card(t)))}
      ${ranked.map(r => row(r.title,
        r.ids.map(id => state.byId.get(id)).filter(visible).map((t, i) => rankedCard(t, i + 1)))).join("")}
    </div>`;
  wireHeader();
}

function renderGrid(active, heading, list, emptyText) {
  document.title = `${heading} — Haukley`;
  app.innerHTML = `${header(active)}
    <main class="page">
      <h1>${esc(heading)}</h1>
      ${list.length ? `<div class="grid">${list.map(t => card(t)).join("")}</div>` : `<p class="empty">${esc(emptyText)}</p>`}
    </main>`;
  wireHeader();
}

function renderSkeleton() {
  app.innerHTML = `<div style="padding:80px var(--gutter) 0"><div class="sk" style="height:min(62vh,44vw,640px);min-height:320px"></div>
    ${[0, 1].map(() => `<div class="sk" style="height:22px;width:220px;margin:34px 0 12px;border-radius:6px"></div>
      <div style="display:flex;gap:8px">${[0, 1, 2, 3, 4].map(() => `<div class="sk" style="flex:1;aspect-ratio:16/9;border-radius:6px"></div>`).join("")}</div>`).join("")}</div>`;
}

// ---------- hover preview ----------

let previewTimer = null;
let previewEl = null;

function hidePreview() {
  clearTimeout(previewTimer);
  previewEl?.remove();
  previewEl = null;
}

function showPreview(tileEl) {
  hidePreview();
  const t = state.byId.get(tileEl.dataset.tid);
  if (!t || !document.body.contains(tileEl)) return;
  const rect = tileEl.getBoundingClientRect();
  const w = Math.max(rect.width * 1.45, 300);
  const gutter = 12;
  let left = rect.left + rect.width / 2 - w / 2;
  left = Math.max(gutter, Math.min(left, innerWidth - w - gutter));
  const picH = (w * 9) / 16;
  const top = Math.max(scrollY + 70, rect.top + scrollY + rect.height / 2 - picH / 2 - 10);
  const { episode, resume } = resumeFor(t);
  const inList = state.myList.has(t.id);
  const len = t.kind === "movie" ? t.runtime : `${t.seasons} Season${t.seasons === 1 ? "" : "s"}`;
  const prog = resume ? `<div class="prog"><div class="bar"><i style="width:${Math.round(pct(resume) * 100)}%"></i></div>
    ${Math.round(resume.position_s / 60)} of ${Math.round(resume.duration_s / 60)}m</div>` : "";
  const el = document.createElement("div");
  el.className = "preview";
  el.style.cssText = `left:${left + scrollX}px;top:${top}px;width:${w}px`;
  el.innerHTML = `
    <div class="pic" data-title="${esc(t.id)}"><img src="${img(t, "card")}" alt=""></div>
    <div class="body">
      <div class="btns">
        <button class="circle solid" data-play="${esc(t.id)}" data-ep="${episode}" aria-label="${resume ? "Resume" : "Play"} ${esc(t.title)}">${ICON.play}</button>
        <button class="circle" data-toggle-list="${esc(t.id)}" aria-label="${inList ? "Remove from" : "Add to"} My List">${inList ? ICON.check : ICON.plus}</button>
        <button class="circle push" data-title="${esc(t.id)}" aria-label="More info">${ICON.down}</button>
      </div>
      <div class="meta"><span class="rating">${esc(t.rating)}</span> ${esc(len)}</div>
      <div class="tags"><span>${esc(t.genre)}</span><span>${t.year}</span>${t.silent ? "<span>Silent film</span>" : ""}${state.rank.has(t.id) ? `<span>Top 10 pick #${state.rank.get(t.id).n}</span>` : ""}</div>
      ${prog}
    </div>`;
  el.addEventListener("mouseleave", hidePreview);
  $("[data-toggle-list]", el).addEventListener("click", async e => {
    e.stopPropagation();
    const b = e.currentTarget;
    await toggleList(t.id);
    const on = state.myList.has(t.id);
    b.innerHTML = on ? ICON.check : ICON.plus;
    b.setAttribute("aria-label", `${on ? "Remove from" : "Add to"} My List`);
  });
  document.body.appendChild(el);
  previewEl = el;
}

document.addEventListener("mouseover", e => {
  if (!hoverable.matches) return;
  const tileEl = e.target.closest(".tile[data-tid]");
  if (!tileEl || tileEl.closest(".preview, .modal")) return;
  if (previewEl && e.relatedTarget && tileEl.contains(e.relatedTarget)) return;
  clearTimeout(previewTimer);
  previewTimer = setTimeout(() => showPreview(tileEl), 450);
});
document.addEventListener("mouseout", e => {
  const tileEl = e.target.closest(".tile[data-tid]");
  if (tileEl && !tileEl.contains(e.relatedTarget)) clearTimeout(previewTimer);
});
addEventListener("resize", hidePreview);

// ---------- title modal ----------

function openTitle(id) {
  hidePreview();
  const t = state.byId.get(id);
  if (!visible(t)) return;
  const modal = $("#modal");
  const box = $(".modal-box", modal);
  const { episode, resume } = resumeFor(t);
  const inList = state.myList.has(t.id);
  const playLabel = resume ? (t.kind === "show" ? `Resume E${episode}` : "Resume") : t.kind === "show" && episode > 1 ? `Play E${episode}` : "Play";
  const eps = t.kind === "show" ? `<h3>Episodes</h3><div class="eps">${t.episodes.map(e => {
    const r = state.progress.get(`${t.id}:${e.number}`);
    return `<button class="ep${e.number === episode ? " current" : ""}" data-play="${esc(t.id)}" data-ep="${e.number}">
      <span class="num">${e.number}</span>
      <span class="thumb"><img src="${ART}${encodeURIComponent(t.id)}/ep${e.number}.jpg" alt="" loading="lazy">${r ? `<span class="bar"><i style="width:${Math.round(pct(r) * 100)}%"></i></span>` : ""}</span>
      <span><span class="name">${esc(e.name)}<span>${e.minutes}m</span></span><p>${esc(e.summary)}</p></span>
    </button>`;
  }).join("")}</div>` : "";
  const more = titles().filter(x => x.id !== t.id && x.kind === t.kind)
    .sort((a, b) => (b.genre === t.genre) - (a.genre === t.genre)).slice(0, 9);
  box.innerHTML = `
    <div class="m-hero" style="background-image:url('${img(t, "backdrop")}')">
      <button class="m-close" data-close aria-label="Close">${ICON.close}</button>
      <div class="m-head">
        ${artTitle(t, "h2", "modal-title")}
        <div class="actions">
          <button class="btn btn-primary" data-play="${esc(t.id)}" data-ep="${t.kind === "show" ? episode : 0}">${ICON.play} ${playLabel}</button>
          <button class="circle" id="list-btn" aria-pressed="${inList}" aria-label="${inList ? "Remove from" : "Add to"} My List">${inList ? ICON.check : ICON.plus}</button>
        </div>
      </div>
    </div>
    <div class="m-body">
      <div class="m-cols">
        <div>
          <div class="meta">${metaLine(t)}</div>
          ${state.rank.has(t.id) ? `<div class="meta" style="margin-top:10px;color:#fff"><span class="chip"><i>TOP 10</i>#${state.rank.get(t.id).n} in ${esc(state.rank.get(t.id).label)}</span></div>` : ""}
          <p class="tagline">${esc(t.tagline)}</p>
          <p class="desc">${esc(t.description)}</p>
        </div>
        <div class="m-side">
          <div><b>Cast:</b> ${esc(t.credits.replace(/^Starring\s*/, "").replace(/ · /g, ", "))}</div>
          <div><b>Genres:</b> ${esc(t.genre)}</div>
          <div><b>Rating:</b> ${t.rating === "NR" ? "Not rated" : esc(t.rating)}</div>
          ${t.silent ? `<div><b>Sound:</b> Silent film (no soundtrack)</div>` : ""}
          ${t.advisory ? `<div class="advisory"><b>Advisory:</b> ${esc(t.advisory)}</div>` : ""}
          ${t.license ? `<div><b>License:</b> ${esc(t.license)}</div>` : ""}
        </div>
      </div>
      ${eps}
      <h3>More Like This</h3>
      <div class="more">${more.map(x => `<button class="more-card" data-title="${esc(x.id)}">
        <img src="${img(x, "card")}" alt="" loading="lazy">
        <div><div class="meta">${metaLine(x)}</div><p>${esc(x.description)}</p></div></button>`).join("")}</div>
    </div>`;
  modal.hidden = false;
  document.body.classList.add("locked");
  modal.scrollTop = 0;
  $("#list-btn").addEventListener("click", async e => {
    const b = e.currentTarget;
    await toggleList(t.id);
    const on = state.myList.has(t.id);
    b.innerHTML = on ? ICON.check : ICON.plus;
    b.setAttribute("aria-pressed", String(on));
    b.setAttribute("aria-label", `${on ? "Remove from" : "Add to"} My List`);
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
  ratedShown: false, seeking: false,
};
const video = player.video;

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
  if (!visible(t)) return;
  if (t.kind === "show" && !(episode >= 1)) episode = resumeFor(t).episode;
  if (t.kind === "movie") episode = 0;
  const e = episode ? t.episodes.find(x => x.number === episode) : null;
  const src = (e || t).stream;
  hidePreview();
  const fromModal = !$("#modal").hidden && location.hash.startsWith("#/title/");
  closeModal(false);
  stopPlayback(false);
  Object.assign(player, { id, episode, sessionId: crypto.randomUUID(), ratedShown: false });
  $("#p-title").innerHTML = e ? `${esc(t.title)}<span>E${e.number} “${esc(e.name)}”</span>` : esc(t.title);
  $("#rated-label").textContent = t.rating === "NR" ? "NOT RATED" : `RATED ${t.rating}`;
  // A content advisory rides on the rating card at the start of playback, like broadcast TV.
  $("#rated-sub").textContent = t.advisory || (t.silent ? `${t.genre} · Silent film, no soundtrack` : t.genre);
  $("#p-error").hidden = true;
  player.el.hidden = false;
  player.el.classList.remove("ad");
  document.body.classList.add("locked");
  const target = `#/play/${encodeURIComponent(id)}/${episode}`;
  // From the title modal the player replaces its history entry, so Back returns to the page.
  if (fromModal) { history.replaceState(null, "", target); state.modalPushed = false; }
  else if (location.hash !== target) history.pushState(null, "", target);

  const r = state.progress.get(`${id}:${episode}`);
  const resumeAt = inProgress(r) ? r.position_s : 0;
  video.controls = false;
  // Safari plays HLS natively (and needs to for AirPlay/iPhone full screen). Newer Chrome also
  // claims native HLS but fails on fMP4 streams, so everything else goes through hls.js.
  const safari = /^((?!chrome|chromium|crios|android|edg).)*safari/i.test(navigator.userAgent);
  const native = video.canPlayType("application/vnd.apple.mpegurl");
  if (native && (safari || !window.Hls?.isSupported())) {
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
  const { adLayer } = player;
  const ima = google.ima;
  const s = { adPlaying: false, contentDone: false, manager: null, contentStarted: false };
  player.ima = s;
  s.container = new ima.AdDisplayContainer(adLayer, video);
  s.container.initialize();
  s.loader = new ima.AdsLoader(s.container);
  const playContent = () => {
    s.contentStarted = true;
    s.adPlaying = false;
    adLayer.classList.remove("on");
    player.el.classList.remove("ad");
    if (!s.contentDone) video.play().catch(() => {});
  };
  s.loader.addEventListener(ima.AdsManagerLoadedEvent.Type.ADS_MANAGER_LOADED, ev => {
    clearTimeout(s.timeout);
    if (s.contentStarted) return; // the timeout already started the film
    const settings = new ima.AdsRenderingSettings();
    settings.restoreCustomPlaybackStateOnAdBreakComplete = true;
    const m = ev.getAdsManager(video, settings);
    s.manager = m;
    const E = ima.AdEvent.Type;
    m.addEventListener(E.CONTENT_PAUSE_REQUESTED, () => {
      s.adPlaying = true;
      video.pause();
      adLayer.classList.add("on");
      player.el.classList.add("ad");
      $("#rated").hidden = true;
    });
    m.addEventListener(E.CONTENT_RESUME_REQUESTED, playContent);
    m.addEventListener(E.STARTED, () => logAdEvent("ad_started"));
    m.addEventListener(E.COMPLETE, () => logAdEvent("ad_completed"));
    m.addEventListener(ima.AdErrorEvent.Type.AD_ERROR, ev => { console.warn("IMA ad error:", ev.getError?.().toString()); playContent(); });
    try {
      m.init(player.el.clientWidth, player.el.clientHeight, ima.ViewMode.NORMAL);
      m.start();
    } catch {
      playContent();
    }
  });
  s.loader.addEventListener(ima.AdErrorEvent.Type.AD_ERROR, ev => { console.warn("IMA ad error:", ev.getError?.().toString()); playContent(); });
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
  const p = $("#p-error");
  p.textContent = text || "Couldn't play this video. Check your connection, then go back and try again.";
  p.hidden = false;
}

function stopPlayback(navigate = true) {
  if (player.id && video.duration && !player.ima?.adPlaying) saveProgress(player.id, player.episode, video.currentTime, video.duration);
  clearInterval(player.saveTimer);
  clearTimeout(player.ratedTimer);
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
  $("#rated").hidden = true;
  $("#p-speed-menu").hidden = true;
  if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
  const wasOpen = !player.el.hidden;
  player.el.hidden = true;
  player.el.classList.remove("playing", "ad", "idle");
  player.id = null;
  document.body.classList.remove("locked");
  if (navigate && wasOpen && location.hash.startsWith("#/play/")) history.back();
}

function poke() {
  player.el.classList.remove("idle");
  clearTimeout(player.idleTimer);
  player.idleTimer = setTimeout(() => {
    if (!video.paused && $("#p-speed-menu").hidden) player.el.classList.add("idle");
  }, 3000);
}

const fmt = s => {
  s = Math.max(0, Math.floor(s || 0));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}` : `${m}:${String(sec).padStart(2, "0")}`;
};
const setPct = (input, v) => input.style.setProperty("--pct", `${Math.round(v * 1000) / 10}%`);

function syncTime() {
  const seek = $("#p-seek");
  const d = video.duration;
  if (!player.seeking && d) {
    seek.value = String(Math.round((video.currentTime / d) * 1000));
    setPct(seek, video.currentTime / d);
  }
  $("#p-remaining").textContent = d ? fmt(d - video.currentTime) : "0:00";
}

function togglePlay() {
  if (player.ima?.adPlaying) return;
  video.paused ? video.play().catch(() => {}) : video.pause();
}
const skip = s => { if (!player.ima?.adPlaying && video.duration) video.currentTime = Math.max(0, Math.min(video.duration - 1, video.currentTime + s)); poke(); };

function toggleFullscreen() {
  if (document.fullscreenElement) return document.exitFullscreen?.();
  if (player.el.requestFullscreen) player.el.requestFullscreen().catch(() => {});
  else if (video.webkitEnterFullscreen) video.webkitEnterFullscreen(); // iPhone Safari
}

video.addEventListener("play", () => { player.el.classList.add("playing"); poke(); });
video.addEventListener("pause", () => {
  player.el.classList.remove("playing");
  poke();
  if (player.id && !player.ima?.adPlaying && video.duration) saveProgress(player.id, player.episode, video.currentTime, video.duration);
});
video.addEventListener("playing", () => {
  if (player.ratedShown || player.ima?.adPlaying) return;
  player.ratedShown = true;
  $("#rated").hidden = false;
  player.ratedTimer = setTimeout(() => { $("#rated").hidden = true; }, state.byId.get(player.id)?.advisory ? 8000 : 5000);
});
video.addEventListener("error", () => { if (player.id && !player.ima?.adPlaying && video.getAttribute("src")) showPlayerError(); });
video.addEventListener("timeupdate", syncTime);
video.addEventListener("durationchange", syncTime);
video.addEventListener("volumechange", () => {
  player.el.classList.toggle("muted", video.muted || video.volume === 0);
  const v = $("#p-volume");
  v.value = String(video.muted ? 0 : video.volume);
  setPct(v, video.muted ? 0 : video.volume);
});
video.addEventListener("ended", () => { if (player.id) saveProgress(player.id, player.episode, video.duration, video.duration); });
video.addEventListener("click", () => { togglePlay(); });
video.addEventListener("dblclick", toggleFullscreen);

const seekInput = $("#p-seek");
seekInput.addEventListener("input", () => {
  player.seeking = true;
  setPct(seekInput, seekInput.value / 1000);
  if (video.duration) $("#p-remaining").textContent = fmt(video.duration * (1 - seekInput.value / 1000));
  poke();
});
seekInput.addEventListener("change", () => {
  if (video.duration && !player.ima?.adPlaying) video.currentTime = (seekInput.value / 1000) * video.duration;
  player.seeking = false;
});
$("#p-volume").addEventListener("input", e => { video.volume = Number(e.target.value); video.muted = video.volume === 0; });
setPct($("#p-volume"), 1);
$("#p-play").addEventListener("click", togglePlay);
$("#p-back10").addEventListener("click", () => skip(-10));
$("#p-fwd10").addEventListener("click", () => skip(10));
$("#p-mute").addEventListener("click", () => { video.muted = !video.muted; if (!video.muted && video.volume === 0) video.volume = 1; });
$("#p-full").addEventListener("click", toggleFullscreen);
$("#p-back").addEventListener("click", () => stopPlayback());
const speedMenu = $("#p-speed-menu");
$("#p-speed").addEventListener("click", e => {
  e.stopPropagation();
  const rates = [0.5, 0.75, 1, 1.25, 1.5];
  speedMenu.innerHTML = `<h4>Playback Speed</h4><div class="opts">${rates.map(r =>
    `<button role="menuitemradio" aria-checked="${video.playbackRate === r}" data-rate="${r}">${r}x${r === 1 ? " (Normal)" : ""}</button>`).join("")}</div>`;
  speedMenu.hidden = !speedMenu.hidden;
  speedMenu.querySelectorAll("[data-rate]").forEach(b => b.addEventListener("click", () => {
    video.playbackRate = Number(b.dataset.rate);
    speedMenu.hidden = true;
  }));
});
player.el.addEventListener("click", e => { if (!e.target.closest(".p-speed")) speedMenu.hidden = true; });
player.el.addEventListener("mousemove", poke);
player.el.addEventListener("touchstart", poke, { passive: true });
addEventListener("resize", () => {
  const m = player.ima?.manager;
  if (m) m.resize(player.el.clientWidth, player.el.clientHeight, google.ima.ViewMode.NORMAL);
});
addEventListener("pagehide", () => {
  if (player.id && video.duration && !player.ima?.adPlaying) saveProgress(player.id, player.episode, video.currentTime, video.duration);
});

// ---------- routing ----------

function route() {
  if (!state.user || !state.profile) return;
  hidePreview();
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
    if (!$("#top")) { state.page = "#/"; renderHome(); }
    return openTitle(decodeURIComponent(title[1]));
  }
  const modal = $("#modal");
  if (!modal.hidden) { modal.hidden = true; document.body.classList.remove("locked"); }
  const sameAsBefore = h === state.page && $("#top");
  const keepY = scrollY;
  state.page = h;
  const param = k => decodeURIComponent((h.split(`${k}=`)[1] || "").split("&")[0]);
  if (h.startsWith("#/movies")) renderKind("movie", param("g"));
  else if (h.startsWith("#/shows")) renderKind("show", param("g"));
  else if (h.startsWith("#/new")) renderNew();
  else if (h.startsWith("#/list")) renderGrid("list", "My List", [...state.myList].map(id => state.byId.get(id)).filter(visible),
    "Nothing here yet. Hover any title (or open it) and choose + to add it.");
  else if (h.startsWith("#/search")) {
    const q = param("q").trim().toLowerCase();
    const hits = titles().filter(t => [t.title, t.genre, t.credits, t.description].join(" ").toLowerCase().includes(q));
    renderGrid("search", q ? `Results for “${q}”` : "Search", hits, "No matches. Try a genre like Drama or Comedy.");
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
  if (!el || el.closest("#player")) return;
  if (el.hasAttribute("data-close")) return closeModal();
  if (el.dataset.title) {
    const target = `#/title/${encodeURIComponent(el.dataset.title)}`;
    hidePreview();
    if (!$("#modal").hidden) location.replace(target); // "More Like This": swap, don't stack
    else { state.modalPushed = true; location.hash = target; }
    return;
  }
  if (el.dataset.playtitle) return startPlayback(el.dataset.playtitle, resumeFor(state.byId.get(el.dataset.playtitle)).episode);
  startPlayback(el.dataset.play, Number(el.dataset.ep || 0));
});
document.addEventListener("keydown", e => {
  if (!player.el.hidden) {
    if (e.target.closest("input") && e.target.type !== "range") return;
    const k = e.key;
    if (k === "Escape") { if (!document.fullscreenElement) stopPlayback(); return; }
    if (k === " " || k === "k") { e.preventDefault(); togglePlay(); poke(); }
    else if (k === "ArrowLeft" || k === "j") { e.preventDefault(); skip(-10); }
    else if (k === "ArrowRight" || k === "l") { e.preventDefault(); skip(10); }
    else if (k === "f") toggleFullscreen();
    else if (k === "m") video.muted = !video.muted;
    return;
  }
  if (e.key === "Escape") { hidePreview(); closeModal(); }
});

function toast(text) {
  document.querySelectorAll(".toast").forEach(t => t.remove());
  const t = document.createElement("div");
  t.className = "toast";
  t.setAttribute("role", "status");
  t.textContent = text;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}

// ---------- boot ----------

async function boot() {
  const { data } = await sb.auth.getSession();
  state.user = data.session?.user || null;
  if (!state.user || state.recovering) {
    stopPlayback(false);
    return renderAuth(state.recovering ? "recover" : "signin");
  }
  renderSkeleton();
  await Promise.all([state.catalog ? null : loadCatalog(), loadProfiles()]);
  // One profile: straight in. Several: ask once per browser tab, like the big streamers do.
  const saved = state.profiles.find(p => p.id === session.get("hk-profile"));
  if (saved || state.profiles.length === 1) {
    state.profile = saved || state.profiles[0];
    await loadViewerData();
    loadIma();
    route();
  } else {
    renderWho(false);
  }
}

sb.auth.onAuthStateChange((event, s) => {
  if (event === "PASSWORD_RECOVERY") { state.recovering = true; return renderAuth("recover"); }
  if (event === "SIGNED_OUT") {
    Object.assign(state, { user: null, profile: null, profiles: [], heroIds: {}, page: null });
    session.set("hk-profile", null);
    state.progress.clear();
    state.myList.clear();
    stopPlayback(false);
    hidePreview();
    $("#modal").hidden = true;
    document.body.classList.remove("locked");
    history.replaceState(null, "", "/watch/");
    renderAuth("signin");
  } else if (s?.user && state.user && s.user.id !== state.user.id) {
    boot();
  }
});

boot().catch(() => {
  app.innerHTML = `<main class="auth"><div class="auth-box"><a class="wordmark" href="/">Haukley<span>.</span></a>
    <h1>Couldn't load Haukley</h1><p class="sub">Check your connection and reload the page.</p></div></main>`;
});
