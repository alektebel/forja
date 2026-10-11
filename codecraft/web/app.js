/* codecraft web — reads /api/state and renders the tree. No framework. */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const fmt = new Intl.NumberFormat("en");
const pct = new Intl.NumberFormat("en", { maximumFractionDigits: 1, style: "percent" });
const fmtPct = (f) => pct.format(f || 0);

const STATE_LABEL = {
  complete: "complete", doing: "in progress", ready: "not started",
  author: "to author", salvage: "port from a branch", legacy: "no checker yet",
  missing: "not in this repo",
};

let STATE = null;

/* ---------------------------------------------------------------- theme */
function effectiveTheme() {
  const saved = localStorage.getItem("codecraft-theme");
  if (saved === "dark" || saved === "light") return saved;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const meta = $('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", theme === "dark" ? "#0d1117" : "#f4f6f8");
  const glyph = $("#theme-glyph");
  if (glyph) glyph.textContent = theme === "dark" ? "☾" : "☀";
  const btn = $("#theme");
  if (btn) {
    const label = theme === "dark" ? "Switch to light theme" : "Switch to dark theme";
    btn.setAttribute("aria-label", label);
    btn.title = label;
  }
}
$("#theme").addEventListener("click", () => {
  const next = effectiveTheme() === "dark" ? "light" : "dark";
  localStorage.setItem("codecraft-theme", next);
  applyTheme(next);
});

function initialTheme() {
  const wanted = new URLSearchParams(location.search).get("theme");
  if (wanted === "dark" || wanted === "light") return wanted;
  return effectiveTheme();
}
applyTheme(initialTheme());

/* ---------------------------------------------------------------- copy */
document.addEventListener("click", async (event) => {
  const btn = event.target.closest(".copy");
  if (!btn) return;
  const target = $(btn.dataset.copy);
  if (!target) return;
  try {
    await navigator.clipboard.writeText(target.textContent.trim());
    const status = btn.parentElement.querySelector(".copied");
    if (status) {
      status.textContent = "copied";
      setTimeout(() => { status.textContent = ""; }, 1600);
    }
  } catch {
    const status = btn.parentElement.querySelector(".copied");
    if (status) status.textContent = "press ⌘/Ctrl-C";
  }
});

/* --------------------------------------------------------------- render */
function renderTotals(t) {
  const cells = [
    ["Complete", `${fmt.format(t.complete)}/${fmt.format(t.courses)}`],
    ["In progress", fmt.format(t.doing)],
    ["Checks", `${fmt.format(t.checks_passed)}/${fmt.format(t.checks_total)}`],
    ["Written", fmtPct(t.repo_fraction)],
  ];
  $("#totals").innerHTML = cells.map(([label, value]) =>
    `<div><dt>${label}</dt><dd>${value}</dd></div>`).join("");
}

function renderNext(next) {
  const card = $("#next");
  if (!next) { card.hidden = true; return; }
  card.hidden = false;
  $("#next-h").textContent = `${next.id} · ${next.title}`;
  $("#next-stage").textContent = `Stage ${next.stage}/${next.checks ? next.checks.total : "?"}`;
  $("#next-file").textContent = next.file;
  $("#next-what").textContent = next.action || next.stage_title || "";
  const predict = $("#next-predict");
  predict.textContent = next.predict || "";
  predict.hidden = !next.predict;
  $("#next-cmd").textContent = next.command;
}

function repoChip(repo) {
  if (!repo || !repo.baseline) return "";
  const label = repo.remaining === 0
    ? "all markers written"
    : `${fmt.format(repo.remaining)} markers left`;
  return `<span class="chip" title="stub markers still standing in the templates">${label}</span>`;
}

function nodeEl(item) {
  const a = document.createElement("a");
  a.className = "node";
  a.href = `?node=${encodeURIComponent(item.id)}`;
  a.dataset.id = item.id;
  a.dataset.state = item.state;
  const checks = item.checks || {};
  const bar = checks.total
    ? `<div class="bar" aria-hidden="true"><div class="bar-fill" style="transform:scaleX(${checks.fraction.toFixed(4)})"></div></div>
       <span class="node-stage">${fmt.format(checks.passed)}/${fmt.format(checks.total)} checks</span>`
    : `<span class="node-stage">${STATE_LABEL[item.state]}</span>`;
  const prereq = (item.prereq || []).map((p) => `<span class="chip">after ${p}</span>`).join("");
  a.setAttribute("aria-label",
    `${item.id} ${item.title}: ${STATE_LABEL[item.state]}` +
    (checks.total ? `, ${checks.passed} of ${checks.total} checks passing` : ""));
  a.innerHTML = `
    <span class="node-top"><span class="node-id">${item.id}</span>
      <span class="node-sym" aria-hidden="true">${item.symbol}</span></span>
    <span class="node-title">${item.title}</span>
    ${bar}
    <span class="node-meta">${repoChip(item.repo)}${prereq}</span>`;
  return a;
}

function renderPhases(phases) {
  const root = $("#phases");
  root.innerHTML = "";
  for (const phase of phases) {
    const section = document.createElement("section");
    section.className = "phase";
    section.id = `phase-${phase.code}`;
    const head = document.createElement("h2");
    head.innerHTML = `<b>${phase.code}</b> · ${phase.title}`;
    section.appendChild(head);
    const grid = document.createElement("div");
    grid.className = "grid";
    for (const item of phase.items) grid.appendChild(nodeEl(item));
    section.appendChild(grid);
    root.appendChild(section);
  }
}

function stageSymbol(status) {
  return { PASS: "✓", FAIL: "✗", ERROR: "✗", TODO: "·" }[status] || "·";
}

function renderDetail(item) {
  if (!item) {
    $("#detail-empty").hidden = false;
    $("#detail-body").hidden = true;
    return;
  }
  $("#detail-empty").hidden = true;
  const body = $("#detail-body");
  body.hidden = false;
  const checks = item.checks || {};
  const repo = item.repo;
  const prereq = (item.prereq || []).length
    ? `<div class="prereq"><span class="kicker">After</span>${item.prereq.map((p) => `<span class="chip">${p}</span>`).join("")}</div>`
    : "";
  const progress = checks.total
    ? `<h3>Checks</h3><div class="bar" aria-hidden="true"><div class="bar-fill" style="transform:scaleX(${checks.fraction.toFixed(4)})"></div></div>
       <p class="dim">${fmt.format(checks.passed)} of ${fmt.format(checks.total)} passing</p>`
    : "";
  const repoBlock = repo && repo.baseline
    ? `<h3>Written</h3><p class="dim">${fmt.format(repo.written)} of ${fmt.format(repo.baseline)} template markers written (${fmtPct(repo.fraction)})</p>`
    : "";
  const stages = (item.stages || []).map((s) => `
    <li>
      <span class="sdot" data-s="${s.status}" aria-hidden="true">${stageSymbol(s.status)}</span>
      <span><span class="stage-file">${s.file}</span> ${s.title}</span>
      <span class="stage-tags">${(s.tags || []).map((t) => `<span class="chip">${t}</span>`).join("")}</span>
    </li>`).join("");
  body.innerHTML = `
    <p class="kicker">${item.id} · ${STATE_LABEL[item.state]}</p>
    <h2>${item.title}</h2>
    <p class="why">${item.why}</p>
    ${prereq}
    ${item.command ? `<div class="cmd"><code id="detail-cmd">${item.command}</code>
      <button type="button" class="copy" data-copy="#detail-cmd" aria-label="Copy the run command">Copy</button>
      <span class="copied" role="status" aria-live="polite"></span></div>` : ""}
    ${progress}
    ${repoBlock}
    ${stages ? `<h3>Stages</h3><ul class="stagelist">${stages}</ul>` : ""}`;
}

function findItem(id) {
  for (const phase of STATE.phases) {
    const hit = phase.items.find((i) => i.id === id);
    if (hit) return hit;
  }
  return null;
}

function select(id, push = true) {
  const item = findItem(id);
  for (const a of $$(".node")) a.setAttribute("aria-current", String(a.dataset.id === id));
  renderDetail(item);
  if (push) {
    const url = item ? `?node=${encodeURIComponent(id)}` : location.pathname;
    history.pushState({ id }, "", url);
  }
}

document.addEventListener("click", (event) => {
  const a = event.target.closest(".node");
  if (!a || event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
  event.preventDefault();
  select(a.dataset.id);
});

addEventListener("popstate", (event) => {
  const id = event.state ? event.state.id : new URLSearchParams(location.search).get("node");
  select(id, false);
});

/* ------------------------------------------------------------- live runs */
/* `cz run` POSTs each attempt to /api/run; this page long-polls /api/events
   and re-renders the moment one lands. CodeCrafters' missing half: the run
   and the page are the same session, no refresh. */
let LAST_SEQ = 0;
let LIVE_POLLING = false;

function liveBadge(event) {
  const el = document.createElement("div");
  el.className = "live-toast";
  el.setAttribute("role", "status");
  const pct = event.total ? Math.round((event.passed / event.total) * 100) : 0;
  el.innerHTML = `<span class="lt-sym">●</span>
    <b>${event.title || event.course}</b>
    <span class="lt-score">${fmt.format(event.passed)}/${fmt.format(event.total)} checks · ${pct}%</span>`;
  document.body.appendChild(el);
  setTimeout(() => el.classList.add("show"), 10);
  setTimeout(() => { el.classList.remove("show"); setTimeout(() => el.remove(), 400); }, 4200);
}

async function refreshState() {
  const res = await fetch("/api/state", { cache: "no-store" });
  STATE = await res.json();
  renderTotals(STATE.totals);
  renderNext(STATE.next);
  renderPhases(STATE.phases);
  const wanted = new URLSearchParams(location.search).get("node");
  select(wanted && findItem(wanted) ? wanted : null, false);
}

function pollEvents() {
  if (LIVE_POLLING) return;
  LIVE_POLLING = true;
  const loop = async () => {
    while (true) {
      try {
        const res = await fetch(`/api/events?since=${encodeURIComponent(LAST_SEQ)}`, { cache: "no-store" });
        const data = await res.json();
        const events = data.events || [];
        if (events.length) {
          LAST_SEQ = events[events.length - 1].seq;
          for (const e of events) liveBadge(e);
          await refreshState();
        }
      } catch {
        await new Promise((r) => setTimeout(r, 5000));   // server gone; retry gently
      }
    }
  };
  loop();
}


/* ----------------------------------------------------------------- init */
async function init() {
  const res = await fetch("/api/state", { cache: "no-store" });
  STATE = await res.json();
  renderTotals(STATE.totals);
  renderNext(STATE.next);
  renderPhases(STATE.phases);
  const wanted = new URLSearchParams(location.search).get("node");
  if (wanted && findItem(wanted)) select(wanted, false);
}

init().then(() => {
  // Replay anything published while the tab was closed, then go live.
  fetch("/api/runs", { cache: "no-store" })
    .then((r) => r.json())
    .then((data) => {
      const events = data.events || [];
      if (events.length) {
        LAST_SEQ = events[events.length - 1].seq;
        if (Date.now() / 1000 - events[events.length - 1].ts < 30) {
          for (const e of events.slice(-1)) liveBadge(e);
        }
      }
      pollEvents();
    })
    .catch(pollEvents);
}).catch((err) => {
  $("#lede").textContent = "Could not read /api/state — is the server still running?";
  console.error(err);
});
