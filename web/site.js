// Haukley site helpers. The key below is Supabase's publishable key: public by design,
// and the waitlist table only accepts inserts (no reads) for it.
window.Haukley = {
  endpoint: "https://axgxpwgbpgcqjxoqwtnv.supabase.co/rest/v1/waitlist",
  key: "sb_publishable_9VpZfDWrMK3orLITxhWZJw_kbAFdw90",
  waitlist(formId, source) {
    const form = document.getElementById(formId);
    if (!form) return;
    const input = form.querySelector("input[type=email]");
    const button = form.querySelector("button");
    const note = form.querySelector(".note");
    const say = (text, cls) => { note.textContent = text; note.className = "note " + (cls || ""); };
    form.addEventListener("submit", async e => {
      e.preventDefault();
      const email = input.value.trim();
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return say("Please enter a valid email address.", "err");
      button.disabled = true;
      say("Adding you…");
      try {
        const r = await fetch(this.endpoint, {
          method: "POST",
          headers: { apikey: this.key, "Content-Type": "application/json", Prefer: "return=minimal" },
          body: JSON.stringify({ email, source }),
        });
        // 409 = already on the list; treat it the same so the form never reveals who signed up.
        if (r.ok || r.status === 409) { say("You're on the list. We'll email you once, at launch.", "ok"); input.value = ""; }
        else say("Something went wrong. Please try again.", "err");
      } catch {
        say("Couldn't reach the server. Check your connection and try again.", "err");
      } finally {
        button.disabled = false;
      }
    });
  },
  // Filmmaker submissions go through the rate-limited submit_film RPC (the table itself is
  // unreadable and unwritable with this key).
  submitFilm(formId) {
    const form = document.getElementById(formId);
    if (!form) return;
    const button = form.querySelector("button[type=submit]");
    const note = form.querySelector(".note");
    const say = (text, cls) => { note.textContent = text; note.className = "note " + (cls || ""); };
    form.addEventListener("submit", async e => {
      e.preventDefault();
      const f = Object.fromEntries(new FormData(form));
      if (f.website) return say("Thanks — we got your film.", "ok"); // honeypot: bots fill every field
      delete f.website;
      for (const k of ["name", "email", "film_title", "screener_url"]) f[k] = (f[k] || "").trim();
      if (!f.name || !f.film_title) return say("Please add your name and the film's title.", "err");
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(f.email)) return say("Please enter a valid email address.", "err");
      if (!/^https:\/\/\S+$/i.test(f.screener_url)) return say("The screener link should start with https://", "err");
      if (!form.rights_confirmed.checked) return say("Please confirm you control the rights.", "err");
      f.rights_confirmed = true;
      button.disabled = true;
      say("Sending…");
      try {
        const r = await fetch(this.endpoint.replace("/waitlist", "/rpc/submit_film"), {
          method: "POST",
          headers: { apikey: this.key, "Content-Type": "application/json" },
          body: JSON.stringify(f),
        });
        if (r.ok) { form.reset(); say("Thanks — we got your film. We'll reply within 30 days.", "ok"); }
        else if (r.status === 400 && (await r.text()).includes("rate limit")) say("Too many submissions today. Email films@haukley.com instead.", "err");
        else say("Something went wrong. Check the fields and try again, or email films@haukley.com.", "err");
      } catch {
        say("Couldn't reach the server. Check your connection and try again.", "err");
      } finally {
        button.disabled = false;
      }
    });
  },
};
