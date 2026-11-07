/* forja web — CodeCrafters-shaped catalog + in-challenge studio.
   Local:  forja web  → /api/state + live /api/events (celebration on pass)
   Static: diegoatencia.dev/forja → state.json (baked)
*/

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
let SELECTED = null; // { kind: "challenge"|"node", id, stageId? }
let LIVE = false;
let LAST_STAGE_MAP = {}; // course → { stageId → status } for pass detection

function basePath() {
  const explicit = document.documentElement.dataset.base;
  if (explicit) return explicit.endsWith("/") ? explicit : `${explicit}/`;
  const path = location.pathname;
  if (path.endsWith("/")) return path;
  if (path.split("/").pop().includes(".")) {
    return path.slice(0, path.lastIndexOf("/") + 1) || "./";
  }
  return `${path}/`;
}

function asset(url) {
  if (!url) return url;
  if (/^(https?:|data:)/i.test(url)) return url;
  if (url.startsWith("/")) return basePath() + url.replace(/^\/+/, "");
  return basePath() + url.replace(/^\.\//, "");
}

async function loadState() {
  try {
    const res = await fetch("/api/state", { cache: "no-store" });
    if (res.ok) {
      LIVE = true;
      return res.json();
    }
  } catch { /* static */ }
  const res = await fetch(asset("state.json"), { cache: "no-store" });
  if (!res.ok) throw new Error(`state.json HTTP ${res.status}`);
  LIVE = false;
  return res.json();
}

/* ---------------------------------------------------------------- theme */
function effectiveTheme() {
  const saved = localStorage.getItem("codecraft-theme");
  if (saved === "dark" || saved === "light") return saved;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const meta = $('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", theme === "dark" ? "#090A0C" : "#f4f5f6");
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
  return localStorage.getItem("codecraft-theme") || "dark";
}
applyTheme(initialTheme());

/* ---------------------------------------------------------------- copy */
document.addEventListener("click", async (event) => {
  const btn = event.target.closest(".copy, .ghost-action[data-copy]");
  if (!btn || !btn.dataset.copy) return;
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

/* --------------------------------------------------------------- catalog */
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
  $("#next-h").textContent = next.headline || next.title || `${next.id} · ${next.label || ""}`;
  $("#next-stage").textContent = `Stage ${next.stage}`;
  $("#next-file").textContent = next.file || "";
  $("#next-what").textContent = next.action || next.stage_title || "";
  $("#next-cmd").textContent = next.command;
  card.onclick = (e) => {
    if (e.target.closest("button")) return;
    if (next.course || next.slug) openStudio("challenge", next.course || next.slug, next.stage);
  };
}

function challengeEl(row) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "challenge";
  btn.dataset.slug = row.slug;
  btn.dataset.state = row.state || "ready";
  btn.setAttribute("role", "listitem");
  const checks = row.checks || {};
  const stageLabel = checks.total
    ? `${fmt.format(checks.passed)}/${fmt.format(checks.total)} stages`
    : `${fmt.format(row.stages)} stages`;
  const stateLabel = STATE_LABEL[row.state] || "";
  btn.setAttribute("aria-label", `${row.headline}: ${stateLabel}`);
  btn.innerHTML = `
    <span class="challenge-logo" aria-hidden="true">
      <img src="${asset(row.logo_url)}" alt="" width="56" height="56">
    </span>
    <span class="challenge-title">${row.headline}</span>
    <span class="challenge-blurb">${row.blurb}</span>
    <span class="challenge-foot">
      <span class="challenge-stages">${stageLabel}</span>
      <span class="challenge-state">${stateLabel}</span>
    </span>`;
  return btn;
}

function renderCatalog(track) {
  const root = $("#catalog");
  root.innerHTML = "";
  for (const row of track) root.appendChild(challengeEl(row));
}

function repoChip(repo) {
  if (!repo || !repo.baseline) return "";
  const label = repo.remaining === 0
    ? "all markers written"
    : `${fmt.format(repo.remaining)} markers left`;
  return `<span class="chip">${label}</span>`;
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
  const logo = item.logo_url
    ? `<img class="node-logo" src="${asset(item.logo_url)}" alt="" width="36" height="36">`
    : "";
  a.innerHTML = `
    <span class="node-top">${logo}<span class="node-id">${item.id}</span>
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

/* --------------------------------------------------------------- studio */
function findChallenge(slug) {
  return (STATE.showcase?.track || []).find((r) => r.slug === slug) || null;
}

function findItem(id) {
  for (const phase of STATE.phases) {
    const hit = phase.items.find((i) => i.id === id);
    if (hit) return hit;
  }
  return null;
}

function studioSource() {
  if (!SELECTED) return null;
  if (SELECTED.kind === "challenge") {
    const row = findChallenge(SELECTED.id);
    if (!row) return null;
    return {
      kind: "challenge",
      id: row.slug,
      title: row.headline,
      kicker: `${row.id} · ${STATE_LABEL[row.state] || ""}`,
      logo_url: row.logo_url,
      command: row.command,
      smoke: row.smoke,
      checks: row.checks,
      stages: row.stages_detail || [],
      slug: row.slug,
    };
  }
  const item = findItem(SELECTED.id);
  if (!item) return null;
  return {
    kind: "node",
    id: item.id,
    title: item.title,
    kicker: `${item.id} · ${STATE_LABEL[item.state]}`,
    logo_url: item.logo_url,
    command: item.command,
    checks: item.checks,
    stages: item.stages || [],
    slug: item.course,
  };
}

function currentStageId(src) {
  if (SELECTED?.stageId != null) {
    const hit = src.stages.find((s) => s.id === SELECTED.stageId);
    if (hit) return hit.id;
  }
  const nextTodo = src.stages.find((s) => s.status !== "PASS");
  return (nextTodo || src.stages[0] || {}).id;
}

function showCatalog() {
  $("#view-catalog").hidden = false;
  $("#studio").hidden = true;
  $("#foot").hidden = false;
  document.body.classList.remove("in-studio");
}

function showStudio() {
  $("#view-catalog").hidden = true;
  $("#studio").hidden = false;
  $("#foot").hidden = true;
  document.body.classList.add("in-studio");
}

function renderStudio() {
  const src = studioSource();
  if (!src || !src.stages.length) {
    showCatalog();
    return;
  }
  showStudio();

  $("#studio-title").textContent = src.title;
  $("#studio-kicker").textContent = src.kicker;
  const logo = $("#studio-logo");
  if (src.logo_url) {
    logo.hidden = false;
    logo.src = asset(src.logo_url);
  } else {
    logo.hidden = true;
  }

  const checks = src.checks || {};
  const passed = checks.passed || src.stages.filter((s) => s.status === "PASS").length;
  const total = checks.total || src.stages.length;
  const frac = total ? passed / total : 0;
  $("#studio-bar").style.transform = `scaleX(${frac.toFixed(4)})`;
  $("#studio-count").textContent = `${fmt.format(passed)}/${fmt.format(total)}`;

  const stageId = currentStageId(src);
  SELECTED.stageId = stageId;

  const rail = $("#stage-rail");
  rail.innerHTML = "";
  for (const s of src.stages) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "rail-item";
    b.dataset.stageId = String(s.id);
    b.dataset.status = s.status;
    if (s.id === stageId) b.setAttribute("aria-current", "true");
    const mark = s.status === "PASS" ? "✓" : s.status === "TODO" ? String(s.id) : "!";
    b.innerHTML = `
      <span class="rail-mark" data-s="${s.status}">${mark}</span>
      <span class="rail-copy">
        <span class="rail-title">Stage ${s.id}: ${s.title}</span>
        <span class="rail-file mono">${s.file || ""}</span>
      </span>`;
    b.addEventListener("click", () => {
      SELECTED.stageId = s.id;
      const q = SELECTED.kind === "challenge"
        ? `?challenge=${encodeURIComponent(SELECTED.id)}&stage=${s.id}`
        : `?node=${encodeURIComponent(SELECTED.id)}&stage=${s.id}`;
      history.pushState({ ...SELECTED }, "", q);
      renderStudio();
    });
    rail.appendChild(b);
  }

  const stage = src.stages.find((s) => s.id === stageId);
  renderStagePane(src, stage);
}

function renderStagePane(src, stage) {
  if (!stage) {
    $("#stage-empty").hidden = false;
    $("#stage-body").hidden = true;
    return;
  }
  $("#stage-empty").hidden = true;
  const body = $("#stage-body");
  body.hidden = false;

  const cmd = src.slug
    ? `forja test ${src.slug} --stage ${stage.id}`
    : (src.command || "");
  const statusLabel = {
    PASS: "passed", FAIL: "failed", ERROR: "error", TODO: "not started",
  }[stage.status] || stage.status;

  const tags = (stage.tags || []).map((t) => `<span class="chip">${t}</span>`).join("");
  const why = stage.why
    ? `<section class="stage-section stage-why"><h3>Why the requirement is what it is</h3><p>${stage.why}</p></section>`
    : "";
  const predict = stage.predict
    ? `<div class="stage-predict"><span class="rail-label">Predict before you look</span><p>${stage.predict}</p></div>`
    : "";
  const action = stage.action
    || "Implement what this stage’s file asks for. The checker names the failure when you get it wrong.";

  body.innerHTML = `
    <p class="stage-status" data-s="${stage.status}">Stage ${stage.id} · ${statusLabel}</p>
    <h2 class="stage-h">Stage ${stage.id}: ${stage.title}</h2>
    <p class="stage-file-line"><span class="mono">${stage.file || ""}</span> ${tags}</p>

    <section class="stage-section">
      <h3>The mechanism</h3>
      <p>${action}</p>
    </section>

    ${why}

    ${predict}

    <section class="stage-section">
      <h3>Your move</h3>
      <ol class="stage-steps">
        <li>Open <code>${stage.file || "the stage file"}</code> in your editor</li>
        <li>Implement the TODO / <code>NotImplementedError</code></li>
        <li>Run the command below</li>
      </ol>
      <div class="cmd">
        <code id="stage-cmd">${cmd}</code>
        <button type="button" class="copy primary-btn" data-copy="#stage-cmd">Copy</button>
        <span class="copied" role="status" aria-live="polite"></span>
      </div>
      <p class="dim stage-hint">When this stage goes green, a tick celebration lands here — keep this tab open with <code>forja web</code>.</p>
    </section>`;
}

function openStudio(kind, id, stageId, push = true) {
  SELECTED = { kind, id, stageId: stageId != null ? Number(stageId) : undefined };
  renderStudio();
  if (push) {
    const key = kind === "challenge" ? "challenge" : "node";
    let url = `?${key}=${encodeURIComponent(id)}`;
    if (SELECTED.stageId != null) url += `&stage=${SELECTED.stageId}`;
    history.pushState({ ...SELECTED }, "", url);
  }
}

function closeStudio(push = true) {
  SELECTED = null;
  showCatalog();
  if (push) history.pushState({}, "", location.pathname);
}

$("#studio-back").addEventListener("click", () => closeStudio(true));

document.addEventListener("click", (event) => {
  const card = event.target.closest(".challenge");
  if (card) {
    event.preventDefault();
    openStudio("challenge", card.dataset.slug);
    return;
  }
  const a = event.target.closest(".node");
  if (!a || event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
  event.preventDefault();
  openStudio("node", a.dataset.id);
});

addEventListener("popstate", (event) => {
  if (event.state?.kind) {
    SELECTED = event.state;
    return renderStudio();
  }
  const params = new URLSearchParams(location.search);
  const challenge = params.get("challenge");
  const node = params.get("node");
  const stage = params.get("stage");
  if (challenge) return openStudio("challenge", challenge, stage, false);
  if (node) return openStudio("node", node, stage, false);
  closeStudio(false);
});

/* ----------------------------------------------------------- celebrate */
function celebratePass({ course, title, stage, file, stageTitle, passed, total }) {
  const root = $("#celebrate");
  $("#celebrate-h").textContent = stage != null
    ? `Stage ${stage} passed`
    : "Checks updated";
  $("#celebrate-sub").textContent = [
    title || course,
    file ? `· ${file}` : "",
    stageTitle ? `— ${stageTitle}` : "",
    total ? `· ${passed}/${total}` : "",
  ].filter(Boolean).join(" ");
  root.hidden = false;
  requestAnimationFrame(() => root.classList.add("show"));
}

function dismissCelebrate() {
  const root = $("#celebrate");
  root.classList.remove("show");
  setTimeout(() => { root.hidden = true; }, 280);
}
$("#celebrate-dismiss").addEventListener("click", dismissCelebrate);
$("#celebrate").addEventListener("click", (e) => {
  if (e.target.id === "celebrate") dismissCelebrate();
});

function snapshotStages() {
  const map = {};
  for (const row of STATE.showcase?.track || []) {
    map[row.slug] = {};
    for (const s of row.stages_detail || []) map[row.slug][s.id] = s.status;
  }
  for (const phase of STATE.phases || []) {
    for (const item of phase.items) {
      if (!item.course || map[item.course]) continue;
      map[item.course] = {};
      for (const s of item.stages || []) map[item.course][s.id] = s.status;
    }
  }
  return map;
}

function detectNewPasses(event) {
  const prev = LAST_STAGE_MAP[event.course] || {};
  const newly = [];
  for (const s of event.stages || []) {
    if (s.status === "PASS" && prev[s.id] !== "PASS") newly.push(s);
  }
  // Fallback: score went up but stages array empty
  if (!newly.length && event.passed > 0) {
    const prevPassed = Object.values(prev).filter((x) => x === "PASS").length;
    if (event.passed > prevPassed) {
      newly.push({
        id: event.next_step ? event.next_step - 1 : event.passed,
        file: "", title: "",
      });
    }
  }
  return newly;
}

/* ------------------------------------------------------------- live runs */
let LAST_SEQ = 0;
let LIVE_POLLING = false;

async function refreshState() {
  STATE = await loadState();
  renderTotals(STATE.totals);
  renderNext(STATE.next);
  renderCatalog(STATE.showcase?.track || []);
  renderPhases(STATE.phases);
  if (SELECTED) renderStudio();
  else showCatalog();
}

function pollEvents() {
  if (!LIVE || LIVE_POLLING) return;
  LIVE_POLLING = true;
  const loop = async () => {
    while (true) {
      try {
        const res = await fetch(`/api/events?since=${encodeURIComponent(LAST_SEQ)}`, { cache: "no-store" });
        const data = await res.json();
        const events = data.events || [];
        if (events.length) {
          LAST_SEQ = events[events.length - 1].seq;
          for (const e of events) {
            const newly = detectNewPasses(e);
            await refreshState();
            LAST_STAGE_MAP = snapshotStages();
            if (newly.length) {
              const s = newly[newly.length - 1];
              // Jump into the challenge studio on the passed (or next) stage
              if (findChallenge(e.course)) {
                openStudio("challenge", e.course, s.id, true);
              }
              celebratePass({
                course: e.course,
                title: e.title,
                stage: s.id,
                file: s.file,
                stageTitle: s.title,
                passed: e.passed,
                total: e.total,
              });
            } else if (findChallenge(e.course)) {
              openStudio("challenge", e.course, undefined, false);
            }
          }
        }
      } catch {
        await new Promise((r) => setTimeout(r, 5000));
      }
    }
  };
  loop();
}

function restoreFromUrl() {
  const params = new URLSearchParams(location.search);
  const challenge = params.get("challenge");
  const node = params.get("node");
  const stage = params.get("stage");
  if (challenge && findChallenge(challenge)) {
    openStudio("challenge", challenge, stage, false);
  } else if (node && findItem(node)) {
    openStudio("node", node, stage, false);
  } else {
    showCatalog();
  }
}

/* ----------------------------------------------------------------- init */
async function init() {
  STATE = await loadState();
  if (STATE.brand?.name) document.title = `${STATE.brand.name} · Challenges`;
  renderTotals(STATE.totals);
  renderNext(STATE.next);
  renderCatalog(STATE.showcase?.track || []);
  renderPhases(STATE.phases);
  LAST_STAGE_MAP = snapshotStages();
  restoreFromUrl();
}

init().then(() => {
  if (!LIVE) return;
  fetch("/api/runs", { cache: "no-store" })
    .then((r) => r.json())
    .then((data) => {
      const events = data.events || [];
      if (events.length) LAST_SEQ = events[events.length - 1].seq;
      pollEvents();
    })
    .catch(pollEvents);
}).catch((err) => {
  $("#lede").textContent = "Could not read state — open via `forja web` or the baked /forja page.";
  console.error(err);
});
