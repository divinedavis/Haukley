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
};
