import "./style.css";

const gate = document.getElementById("gate");

const loginX = document.getElementById("login-x");
if (loginX?.classList.contains("is-soon")) {
  loginX.addEventListener("click", (e) => {
    e.preventDefault();
  });
}

const panel = document.getElementById("panel");
const term = document.getElementById("term");
const form = document.getElementById("composer");
const input = document.getElementById("input");
const whoami = document.getElementById("whoami");
const logoutBtn = document.getElementById("logout");

const EMOJI_RE =
  /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}\u{200D}]/gu;

const WELCOME =
  "Frong hopped on. We can talk shop, roast a launchpad thesis, or dig into a wallet when you are ready — your call.";

function scrub(text, { trim = false } = {}) {
  // Don't trim by default — streamed tokens often begin with a space.
  const out = String(text || "").replace(EMOJI_RE, "");
  return trim ? out.trim() : out;
}

function money(n) {
  const v = Number(n);
  if (!Number.isFinite(v)) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function addLine(role, text, { typing = false } = {}) {
  const el = document.createElement("div");
  el.className = `line ${role}`;
  if (role === "sys" || role === "err" || role === "status") {
    el.textContent = text;
  } else {
    const who = document.createElement("span");
    who.className = "who";
    who.textContent = role === "user" ? "You" : "Frong";
    const body = document.createElement("span");
    body.className = "body";
    if (typing) body.classList.add("typing");
    body.textContent = text;
    el.append(who, body);
  }
  term.appendChild(el);
  term.scrollTop = term.scrollHeight;
  return el;
}

function setBody(el, text, { typing = false } = {}) {
  const body = el.querySelector(".body");
  if (!body) return;
  body.textContent = text;
  body.classList.toggle("typing", typing);
  term.scrollTop = term.scrollHeight;
}

function ensureWelcome() {
  if (term.children.length) return;
  addLine("bot", WELCOME);
}

function renderReport(report) {
  if (!report || report.ok === false) {
    if (report?.error) addLine("err", report.error);
    return;
  }
  const rows = report.track?.length ? report.track : report.ranked || [];
  if (!rows.length && !report.migrations_covered && report.tool !== "dune_snapshot") {
    return;
  }
  const card = document.createElement("div");
  card.className = "report";
  const title = document.createElement("h4");
  if (report.tool === "analyze_ca") {
    title.textContent = `CA ${report.prefix_ca || ""} · track these`;
  } else if (report.tool === "dune_snapshot") {
    title.textContent = "Frong activity";
  } else {
    title.textContent = "Wallet stats";
  }
  card.appendChild(title);

  if (report.tool === "dune_snapshot") {
    const p = document.createElement("div");
    p.textContent = `events ${report.recent_events} · migrations ${report.migrations_covered} · analyses ${report.analyses} · track hits ${report.trackable_hits}`;
    card.appendChild(p);
    term.appendChild(card);
    term.scrollTop = term.scrollHeight;
    return;
  }

  const table = document.createElement("table");
  for (const r of rows.slice(0, 8)) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${r.rank || ""} ${r.prefix || ""}</td>
      <td class="num">score ${r.score ?? "—"}</td>
      <td class="num">pnl ${money(r.total_profit)}</td>
      <td class="num">wr ${r.winrate_30d ?? "—"}%</td>`;
    table.appendChild(tr);
  }
  card.appendChild(table);
  term.appendChild(card);
  term.scrollTop = term.scrollHeight;
}

async function loadSession() {
  const res = await fetch("/api/me", { credentials: "include" });
  const data = await res.json();
  if (!data.user) {
    gate.classList.remove("hidden");
    panel.classList.add("hidden");
    return null;
  }
  gate.classList.add("hidden");
  panel.classList.remove("hidden");
  whoami.textContent = `@${data.user.handle}`;
  return data.user;
}

async function loadHistory() {
  const res = await fetch("/api/chat", { credentials: "include" });
  if (!res.ok) return;
  const data = await res.json();
  term.innerHTML = "";
  for (const m of data.messages || []) {
    if (m.role === "user") addLine("user", m.content || "");
    if (m.role === "assistant") {
      addLine("bot", scrub(m.content || ""));
      if (m.report) renderReport(m.report);
    }
  }
  ensureWelcome();
}

async function sendMessage(text) {
  addLine("user", text);
  const botEl = addLine("bot", "", { typing: true });
  let full = "";

  const res = await fetch("/api/chat", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: text }),
  });

  if (res.status === 401) {
    setBody(botEl, "", { typing: false });
    botEl.remove();
    addLine("err", "Login required");
    await loadSession();
    return;
  }
  if (!res.ok) {
    setBody(botEl, "", { typing: false });
    botEl.remove();
    addLine("err", await res.text());
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const chunks = buf.split("\n\n");
    buf = chunks.pop() || "";
    for (const block of chunks) {
      const line = block.trim();
      if (!line.startsWith("data:")) continue;
      let ev;
      try {
        ev = JSON.parse(line.slice(5).trim());
      } catch {
        continue;
      }
      if (ev.type === "status") addLine("status", ev.message);
      if (ev.type === "report") renderReport(ev.report);
      if (ev.type === "token") {
        full += ev.text || "";
        setBody(botEl, scrub(full), { typing: true });
      }
      if (ev.type === "cleared") {
        term.innerHTML = "";
        full = "";
        ensureWelcome();
      }
      if (ev.type === "error") {
        setBody(botEl, "", { typing: false });
        botEl.remove();
        addLine("err", ev.error || "error");
        return;
      }
      if (ev.type === "done") {
        setBody(botEl, scrub(ev.assistant || full), { typing: false });
      }
    }
  }
  setBody(botEl, scrub(full) || "(empty)", { typing: false });
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text || input.disabled) return;
  input.value = "";
  input.disabled = true;
  try {
    await sendMessage(text);
  } catch (err) {
    addLine("err", String(err.message || err));
  } finally {
    input.disabled = false;
    input.focus();
  }
});

logoutBtn.addEventListener("click", async () => {
  await fetch("/auth/logout", { method: "POST", credentials: "include" });
  term.innerHTML = "";
  await loadSession();
});

async function boot() {
  const user = await loadSession();
  if (user) await loadHistory();
  input.focus();
}

boot().catch((err) => {
  console.error(err);
  gate.classList.remove("hidden");
});
