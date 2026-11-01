/* Mira GUI - vanilla JS, Artha-inspired dark theme. No em/en dashes. */
"use strict";

// ---------- API ----------

async function api(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({ detail: "Server returned an unexpected response." }));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

const get  = p => api("GET", p);
const post = (p, b) => api("POST", p, b);

// ---------- HTML escape ----------

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// ---------- inline SVG icons ----------

const SVG = {
  zap:      `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`,
  copy:     `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="14" height="14" x="8" y="8" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>`,
  download: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>`,
  alert:    `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>`,
  check:    `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/></svg>`,
  info:     `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>`,
  x:        `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/></svg>`,
  external: `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></svg>`,
  clock:    `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
  hash:     `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="4" x2="20" y1="9" y2="9"/><line x1="4" x2="20" y1="15" y2="15"/><line x1="10" x2="8" y1="3" y2="21"/><line x1="16" x2="14" y1="3" y2="21"/></svg>`,
};

// ---------- markdown renderer ----------

function renderMd(md) {
  if (!md) return "";
  let s = md
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  s = s.replace(/```[\s\S]*?```/g, m => {
    const inner = m.slice(3, -3).replace(/^\w*\n/, "");
    return `<pre><code>${inner}</code></pre>`;
  });
  s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
  s = s.replace(/^### (.+)$/gm, "<h3>$1</h3>");
  s = s.replace(/^## (.+)$/gm,  "<h2>$1</h2>");
  s = s.replace(/^# (.+)$/gm,   "<h1>$1</h1>");
  s = s.replace(/^---$/gm, "<hr>");
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/_([^_]+)_/g, "<em>$1</em>");
  s = s.replace(/((?:^\|.+\|\n)+)/gm, tbl => {
    const rows = tbl.trim().split("\n").filter(r => !/^\|[-:| ]+\|$/.test(r));
    if (rows.length < 1) return tbl;
    const cells = r => r.replace(/^\|/, "").replace(/\|$/, "").split("|").map(c => c.trim());
    const head = cells(rows[0]).map(c => `<th>${c}</th>`).join("");
    const body = rows.slice(1).map(r => cells(r).map(c => `<td>${c}</td>`).join("")).map(r => `<tr>${r}</tr>`).join("");
    return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
  });
  s = s.replace(/((?:^[-*] .+\n?)+)/gm, block => {
    const items = block.trim().split("\n").map(l => `<li>${l.replace(/^[-*] /, "")}</li>`).join("");
    return `<ul>${items}</ul>`;
  });
  s = s.replace(/((?:^\d+\. .+\n?)+)/gm, block => {
    const items = block.trim().split("\n").map(l => `<li>${l.replace(/^\d+\. /, "")}</li>`).join("");
    return `<ol>${items}</ol>`;
  });
  s = s.replace(/^(?!<[a-z]|$)(.+)$/gm, "<p>$1</p>");
  return s;
}

// ---------- chips ----------

const STATUS_CHIP = {
  ok:                  ["ok",           "chip-ok"],
  held:                ["held",         "chip-held"],
  insufficient:        ["insufficient", "chip-insuf"],
  declined:            ["declined",     "chip-declined"],
  verification_failed: ["verify failed","chip-failed"],
  unclear:             ["unclear",      "chip-unclear"],
};

function chipHtml(status) {
  const [label, cls] = STATUS_CHIP[status] || [esc(status), "chip-unclear"];
  const iconMap = { ok: SVG.check, held: SVG.alert, insufficient: SVG.info,
                    declined: SVG.x, verification_failed: SVG.x, unclear: SVG.info };
  return `<span class="chip ${cls}">${iconMap[status] || ""}${label}</span>`;
}

function conflictStatusChip(status) {
  const map = {
    open:          ["open",          "chip-open",     SVG.alert],
    resolved:      ["resolved",      "chip-resolved", SVG.check],
    awaiting_data: ["awaiting data", "chip-awaiting", SVG.info],
  };
  const [label, cls, ic] = map[status] || [esc(status), "chip-unclear", ""];
  return `<span class="chip ${cls}">${ic}${label}</span>`;
}

// ---------- toast ----------

function toast(msg, isError = false) {
  const el = document.createElement("div");
  el.style.cssText = `
    position:fixed;bottom:24px;right:24px;padding:11px 18px;
    border-radius:10px;font-size:.875rem;font-weight:500;
    font-family:var(--font-sans);
    z-index:9999;max-width:380px;
    background:${isError ? "var(--red)" : "var(--emerald)"};
    color:#fff;box-shadow:0 8px 24px rgba(0,0,0,0.4);
    pointer-events:none;
    animation:fadeInUp .2s ease;
  `;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

// ---------- copy ----------

async function copyText(text, btn) {
  try {
    await navigator.clipboard.writeText(text);
    const orig = btn.innerHTML;
    btn.innerHTML = SVG.check + " Copied";
    setTimeout(() => { btn.innerHTML = orig; }, 1600);
  } catch {
    toast("Copy failed. Select text manually.", true);
  }
}

// ---------- global state ----------

let config = {};
let lastRunResult = null;
let allConflicts = [];
let allRuns = [];
let openConflictId = null;

// ---------- nav ----------

const TAB_TITLES = {
  ask: "Ask Mira",
  conflicts: "Conflict Queue",
  dashboard: "Status Dashboard",
  history: "Run History",
};

function switchTab(name) {
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(b => b.classList.remove("active"));

  const screen = document.getElementById(`screen-${name}`);
  const btn = document.querySelector(`.nav-item[data-tab="${name}"]`);
  if (screen) screen.classList.add("active");
  if (btn) btn.classList.add("active");

  const titleEl = document.getElementById("topbar-title");
  if (titleEl) titleEl.textContent = TAB_TITLES[name] || name;

  const actionsEl = document.getElementById("topbar-actions");
  if (actionsEl) {
    actionsEl.innerHTML = "";
    if (name === "dashboard") {
      actionsEl.innerHTML = `<button class="btn btn-secondary btn-sm" onclick="loadDashboard()">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/></svg>
        Refresh
      </button>`;
    }
  }

  if (name === "dashboard") loadDashboard();
  if (name === "conflicts") loadConflicts();
  if (name === "history")   loadRuns();
}

// ---------- SCREEN A: Ask Mira ----------

async function submitAsk() {
  const request = document.getElementById("ask-request").value.trim();
  if (!request) { toast("Please enter a request.", true); return; }

  const audience = document.getElementById("ask-audience").value || null;
  const model    = document.getElementById("ask-model").value;
  const asOfVal  = document.getElementById("ask-asof").value;
  const useT     = document.getElementById("ask-usetoday").checked;

  const btn = document.getElementById("ask-submit");
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Asking...`;

  const reportEl = document.getElementById("ask-report");
  const chipsEl  = document.getElementById("ask-report-header-chips");
  reportEl.innerHTML = `<div class="state-box"><span class="spinner"></span><span>Running pipeline...</span></div>`;
  if (chipsEl) chipsEl.innerHTML = "";

  try {
    const result = await post("/api/ask", {
      request, audience, model,
      as_of: useT ? null : (asOfVal || config.default_as_of),
      use_today: useT,
    });
    lastRunResult = result;
    renderAskResult(result);
    updateConflictBadge();
  } catch (err) {
    reportEl.innerHTML = `<div class="error-box">${SVG.x} ${esc(err.message)}</div>`;
    if (chipsEl) chipsEl.innerHTML = "";
  } finally {
    btn.disabled = false;
    btn.innerHTML = `${SVG.zap} Ask Mira`;
  }
}

function renderAskResult(r) {
  const reportEl = document.getElementById("ask-report");
  const chipsEl  = document.getElementById("ask-report-header-chips");
  if (chipsEl) chipsEl.innerHTML = chipHtml(r.status);

  let html = "";

  // Held banner with conflict evidence cards
  if (r.status === "held" && r.conflicts && r.conflicts.length > 0) {
    const conflictCards = r.conflicts.map(c => {
      const evFields = Object.entries(c.evidence || {})
        .map(([k, v]) => `${esc(k)}: <strong>${esc(v)}</strong>`)
        .join(" &middot; ");
      return `<div class="held-conflict-card">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:4px;">
          <span class="held-conflict-id">${esc(c.id)}</span>
          <button class="btn btn-xs btn-secondary" onclick="switchTab('conflicts');setTimeout(()=>openConflictDetail('${esc(c.id)}'),300)">
            View in queue
          </button>
        </div>
        <div class="held-conflict-evidence">${evFields}</div>
      </div>`;
    }).join("");

    const heldOutputs = r.conflicts.flatMap(c => c.affects || []).filter((v,i,a) => a.indexOf(v)===i);

    html += `<div class="held-banner">
      <div class="held-banner-title">${SVG.alert} Output held: unresolved data conflicts</div>
      <p class="text-sm text-muted" style="margin-bottom:10px;">
        Resolve each conflict in the queue, then re-run this request.
        Held outputs: <span class="text-amber bold">${esc(heldOutputs.join(", ") || "none")}</span>
      </p>
      ${conflictCards}
      <div class="held-disclaimer">
        Until these conflicts are resolved, this output is held and the testing phase cannot proceed.
        Unresolved data conflicts are a project risk.
      </div>
      <div style="margin-top:12px;">
        <button class="btn btn-secondary btn-sm" onclick="logRiskNote(this)">
          ${SVG.copy} Log as a risk note (copy to clipboard)
        </button>
      </div>
    </div>`;
  }

  // Insufficient
  if (r.status === "insufficient" && r.missing && r.missing.length > 0) {
    const items = r.missing.map(m => `<li>${esc(m)}</li>`).join("");
    html += `<div class="info-box" style="margin-bottom:14px;">
      <div style="font-weight:600;margin-bottom:6px;">${SVG.info} Missing information required:</div>
      <ul style="margin-left:16px;font-size:.875rem;margin-top:4px;">${items}</ul>
    </div>`;
  }

  // Declined
  if (r.status === "declined") {
    html += `<div style="padding:20px;background:var(--violet-bg);border:1px solid var(--violet-border);border-radius:var(--radius-sm);font-size:.875rem;color:var(--violet);margin-bottom:14px;">
      ${SVG.x} <strong style="color:var(--violet);">Request declined</strong>
      <p style="margin-top:6px;color:var(--text2);">${esc(r.markdown || "Mira does not respond to this type of request.")}</p>
    </div>`;
  }

  // Markdown report
  if (r.markdown && r.status !== "declined") {
    html += `<div class="md-report">${renderMd(r.markdown)}</div>`;
  }

  // Run meta
  if (r.usage || r.trace_id) {
    const u = r.usage || {};
    const tid = r.trace_id || "";
    html += `<div class="run-meta">
      ${u.prompt_tokens != null ? `<span class="run-meta-item">${SVG.hash} ${u.prompt_tokens}+${u.completion_tokens ?? 0} tok</span>` : ""}
      ${u.cost_usd != null ? `<span class="run-meta-item">\$${u.cost_usd.toFixed(6)}</span>` : ""}
      ${tid ? `<span class="run-meta-item">${SVG.clock}
        <button class="trace-id-link" title="Click to copy trace ID" onclick="navigator.clipboard.writeText('${esc(tid)}').then(()=>toast('Trace ID copied.'))">
          ${esc(tid.slice(0,14))}...
        </button></span>` : ""}
    </div>`;
  }

  // Draft notice
  html += `<div class="draft-notice">
    <span>Draft prepared by Mira. Not shared. Pending PM/TPM review and approval.</span>
    <span style="display:flex;gap:6px;">
      <button class="btn btn-secondary btn-xs" id="btn-copy-report">${SVG.copy} Copy</button>
      <button class="btn btn-secondary btn-xs" id="btn-dl-report">${SVG.download} Download .md</button>
    </span>
  </div>`;

  reportEl.innerHTML = html;

  document.getElementById("btn-copy-report")?.addEventListener("click", function() {
    copyText(lastRunResult?.markdown || "", this);
  });
  document.getElementById("btn-dl-report")?.addEventListener("click", () => {
    const blob = new Blob([lastRunResult?.markdown || ""], { type: "text/markdown" });
    const a = Object.assign(document.createElement("a"), {
      href: URL.createObjectURL(blob), download: "mira-report.md"
    });
    a.click();
  });
}

async function logRiskNote(btn) {
  const ids = (lastRunResult?.conflicts || []).map(c => c.id).join(", ");
  const outputs = (lastRunResult?.conflicts || []).flatMap(c => c.affects || []).filter((v,i,a)=>a.indexOf(v)===i).join(", ");
  const text = `RISK NOTE (draft - not submitted to register)\n` +
    `Unresolved data conflicts detected by Mira.\n` +
    `Held outputs: ${outputs}.\nConflicts: ${ids}.\n` +
    `Action required: data owner review and PM/TPM sign-off before the testing phase proceeds.\n` +
    `Date: ${new Date().toISOString().slice(0,10)}`;
  await copyText(text, btn);
}

// ---------- SCREEN B: Conflicts ----------

async function loadConflicts() {
  const listEl = document.getElementById("conflicts-list");
  listEl.innerHTML = `<div class="state-box"><span class="spinner"></span><span>Loading...</span></div>`;
  document.getElementById("conflict-detail").style.display = "none";

  try {
    const data = await get(`/api/conflicts?as_of=${encodeURIComponent(config.default_as_of || "")}`);
    allConflicts = data.conflicts || [];
    renderConflictTable(allConflicts, data.held_outputs || []);
  } catch (err) {
    listEl.innerHTML = `<div class="card-body"><div class="error-box">${SVG.x} ${esc(err.message)}</div></div>`;
  }
}

function renderConflictTable(conflicts, heldOutputs) {
  const el = document.getElementById("conflicts-list");

  if (conflicts.length === 0) {
    el.innerHTML = `<div class="state-box">${SVG.check}<span>No conflicts detected.</span></div>`;
    return;
  }

  const heldBanner = heldOutputs.length
    ? `<div class="card-body-sm" style="border-bottom:1px solid var(--border2);">
        <div class="info-box" style="font-size:.82rem;">
          ${SVG.info} Held outputs: <strong>${esc(heldOutputs.join(", "))}</strong>
          <span style="color:var(--text3);margin-left:6px;">Blocked until all open conflicts are signed.</span>
        </div>
       </div>`
    : "";

  const rows = conflicts.map(c => {
    const task = c.evidence?.task || "";
    return `<tr class="clickable" onclick="openConflictDetail('${esc(c.id)}')">
      <td class="mono" style="color:var(--text2);font-size:.8rem;">${esc(c.id)}</td>
      <td style="color:var(--text2);font-size:.82rem;">${esc(c.type.replace(/_/g," "))}</td>
      <td class="mono" style="font-size:.82rem;">${esc(task)}</td>
      <td>${c.affects.map(a => `<span class="chip chip-insuf" style="margin:1px;font-size:.68rem;">${esc(a)}</span>`).join(" ")}</td>
      <td>${conflictStatusChip(c.status)}</td>
    </tr>`;
  }).join("");

  el.innerHTML = `${heldBanner}
  <div class="tbl-wrap">
    <table>
      <thead><tr>
        <th>ID</th><th>Type</th><th>Task</th><th>Affects</th><th>Status</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
  </div>`;
}

function openConflictDetail(id) {
  openConflictId = id;
  const c = allConflicts.find(x => x.id === id);
  if (!c) return;

  // Highlight row
  document.querySelectorAll("#conflicts-list tbody tr").forEach(tr => tr.classList.remove("row-active"));
  const rows = document.querySelectorAll("#conflicts-list tbody tr");
  rows.forEach(tr => { if (tr.textContent.includes(id)) tr.classList.add("row-active"); });

  const panel = document.getElementById("conflict-detail");
  panel.style.display = "block";
  panel.scrollIntoView({ behavior: "smooth", block: "nearest" });

  // Evidence grid
  const evidenceItems = Object.entries(c.evidence || {}).map(([k, v]) => `
    <div class="evidence-item">
      <div class="evidence-key">${esc(k)}</div>
      <div class="evidence-val">${esc(v)}</div>
    </div>`).join("");

  // Decision log
  let decisionHtml = "";
  if (c.decision) {
    const d = c.decision;
    decisionHtml = `<div class="decision-log">
      <div class="decision-log-who">${SVG.check} Signed: ${esc(d.outcome)} by ${esc(d.decided_by)} on ${esc(d.date || "")}</div>
      <div class="decision-log-rationale">"${esc(d.rationale)}"</div>
    </div>`;
  }
  if (c.note) {
    decisionHtml += `<div class="expiry-note">${SVG.alert} ${esc(c.note)}</div>`;
  }

  const OUTCOMES = [
    { val: "data_correct",     label: "Data correct",    desc: "The evidence is accurate; the conflict is a labelling ambiguity." },
    { val: "typo",             label: "Typo",            desc: "One source value is a known typo; the other is correct." },
    { val: "more_data_needed", label: "More data needed",desc: "Cannot decide yet; flag for further investigation." },
    { val: "provisional",      label: "Provisional",     desc: "Accepting this value provisionally pending confirmation." },
  ];

  const outcomeHtml = OUTCOMES.map(o => `
    <label class="outcome-option">
      <input type="radio" name="sign-outcome" value="${o.val}">
      <div>
        <div class="outcome-label">${esc(o.label)}</div>
        <div class="outcome-desc">${esc(o.desc)}</div>
      </div>
    </label>`).join("");

  panel.innerHTML = `<div class="card">
    <div class="card-header">
      <span class="card-title mono">${esc(c.id)}</span>
      <span style="display:flex;align-items:center;gap:8px;">
        ${conflictStatusChip(c.status)}
      </span>
    </div>
    <div class="card-body">
      <p class="text-sm text-muted" style="margin-bottom:14px;">
        Type: <strong style="color:var(--text)">${esc(c.type.replace(/_/g," "))}</strong>
        &nbsp;&middot;&nbsp; Holds: <strong style="color:var(--amber)">${esc(c.affects.join(", "))}</strong>
      </p>

      <div class="section-heading">Raw evidence (exactly as returned by the data checker)</div>
      <div class="evidence-grid">${evidenceItems}</div>

      ${decisionHtml}

      <div class="expiry-note" style="margin-top:12px;">
        ${SVG.hash} Decision fingerprint: <code>${esc(c.fingerprint)}</code>
        &nbsp;&middot;&nbsp; Expires automatically if the underlying data changes.
      </div>

      <div class="section-heading" style="margin-top:22px;">Sign a decision</div>
      <form id="sign-form" onsubmit="submitSign(event)">
        <div class="field">${outcomeHtml}</div>
        <div class="row-fields">
          <div class="field">
            <label class="field-label" for="sign-name">Your name (required)</label>
            <input type="text" id="sign-name" placeholder="Full name" required>
          </div>
        </div>
        <div class="field">
          <label class="field-label" for="sign-rationale">Reason (required)</label>
          <textarea id="sign-rationale" rows="3" placeholder="Explain why this decision is correct" required></textarea>
        </div>
        <div id="sign-error" class="error-box gap-top-sm" style="display:none;"></div>
        <div style="margin-top:14px;">
          <button type="submit" class="btn btn-primary" id="sign-submit">
            ${SVG.check} Record decision
          </button>
        </div>
      </form>
    </div>
  </div>`;
}

async function submitSign(event) {
  event.preventDefault();
  const outcome   = document.querySelector('input[name="sign-outcome"]:checked')?.value;
  const name      = document.getElementById("sign-name").value.trim();
  const rationale = document.getElementById("sign-rationale").value.trim();
  const errEl     = document.getElementById("sign-error");
  errEl.style.display = "none";

  if (!outcome)  { errEl.textContent = "Please select an outcome."; errEl.style.display = "block"; return; }
  if (!name)     { errEl.textContent = "Name is required.";         errEl.style.display = "block"; return; }
  if (!rationale){ errEl.textContent = "Reason is required.";       errEl.style.display = "block"; return; }

  const btn = document.getElementById("sign-submit");
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Saving...`;

  try {
    await post(`/api/conflicts/${encodeURIComponent(openConflictId)}/sign`,
               { outcome, decided_by: name, rationale });
    toast("Decision recorded.");
    await loadConflicts();
    if (openConflictId) openConflictDetail(openConflictId);
    updateConflictBadge();
  } catch (err) {
    errEl.textContent = err.message;
    errEl.style.display = "block";
    btn.disabled = false;
    btn.innerHTML = `${SVG.check} Record decision`;
  }
}

// ---------- SCREEN C: Dashboard ----------

async function loadDashboard() {
  const el = document.getElementById("dashboard-content");
  el.innerHTML = `<div class="state-box"><span class="spinner"></span><span>Loading...</span></div>`;
  try {
    const d = await get(`/api/dashboard?as_of=${encodeURIComponent(config.default_as_of || "")}`);
    renderDashboard(d);
  } catch (err) {
    el.innerHTML = `<div class="error-box">${SVG.x} ${esc(err.message)}</div>`;
  }
}

function renderDashboard(d) {
  const el = document.getElementById("dashboard-content");
  const level = (d.health?.level || "unknown").toLowerCase();
  const reasons = (d.health?.reasons || []).map(r => `<li style="margin-bottom:3px;">${esc(r)}</li>`).join("");
  const counts = d.counts || {};

  const STAT_DEFS = [
    { key: "Done",       color: "var(--emerald)", label: "Done",       bg: "var(--emerald-bg)", border: "var(--emerald-border)" },
    { key: "In Progress",color: "var(--gold)",    label: "In Progress",bg: "var(--gold-bg)",    border: "var(--gold-border)" },
    { key: "Blocked",    color: "var(--red)",     label: "Blocked",    bg: "var(--red-bg)",     border: "var(--red-border)" },
    { key: "To Do",      color: "var(--text2)",   label: "To Do",      bg: "var(--card2)",      border: "var(--border)" },
    { key: "total",      color: "var(--text)",    label: "Total",      bg: "var(--card2)",      border: "var(--border)" },
  ];

  const tiles = STAT_DEFS.map(s => `
    <div class="stat-tile">
      <div class="st-icon">
        <div class="icon-badge" style="background:${s.bg};border:1px solid ${s.border};">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="${s.color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/></svg>
        </div>
      </div>
      <div class="st-num" style="color:${s.color};">${counts[s.key] ?? 0}</div>
      <div class="st-label">${esc(s.label)}</div>
    </div>`).join("");

  // At risk rows
  const atRiskRows = (d.at_risk || []).map(t =>
    `<tr><td class="mono" style="font-size:.8rem;">${esc(t.id)}</td>
     <td class="text-sm">${esc(t.due || "")}</td>
     <td class="text-sm text-muted">${(t.reasons||[]).map(r=>esc(r)).join(", ")}</td></tr>`
  ).join("") || `<tr><td colspan="3" class="state-box" style="padding:16px;text-align:left;color:var(--text3);">None</td></tr>`;

  // Blocked rows
  const blockedRows = (d.blocked || []).map(t =>
    `<tr><td class="mono" style="font-size:.8rem;">${esc(t.id)}</td>
     <td class="text-sm">${esc(t.name)}</td>
     <td class="text-sm">${esc(t.due || "")}</td>
     <td class="text-sm text-muted">${esc(t.assignee || "")}</td></tr>`
  ).join("") || `<tr><td colspan="4" class="state-box" style="padding:16px;text-align:left;color:var(--text3);">None</td></tr>`;

  // Milestones
  const msRows = (d.upcoming_milestones || []).map(m =>
    `<tr><td class="text-sm">${esc(m.name)}</td>
     <td class="mono" style="font-size:.8rem;color:var(--amber);">${esc(m.due)}</td>
     <td class="text-sm text-muted">Phase ${esc(m.phase)}</td></tr>`
  ).join("") || `<tr><td colspan="3" class="state-box" style="padding:16px;text-align:left;color:var(--text3);">None in window</td></tr>`;

  // Workload
  const wlRows = (d.workload || []).map(w =>
    `<tr><td class="text-sm bold">${esc(w.person)}</td>
     <td class="mono" style="font-size:.8rem;">${w.total ?? 0}</td>
     <td class="mono" style="font-size:.8rem;color:var(--amber);">${w.open ?? 0}</td>
     <td class="text-sm text-muted">${Object.entries(w.by_status||{}).map(([s,n])=>`${esc(s)}: ${n}`).join(", ")}</td></tr>`
  ).join("") || `<tr><td colspan="4" style="padding:14px;color:var(--text3);font-size:.82rem;">No data</td></tr>`;

  const openConf = d.open_conflicts_count ?? 0;
  const confEl = openConf > 0
    ? `<div class="amber-box" style="display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 14px;background:var(--amber-bg);border:1px solid var(--amber-border);border-radius:var(--radius-sm);">
        <span class="text-sm" style="color:var(--amber);">${SVG.alert} <strong>${openConf}</strong> open conflict${openConf>1?"s":""}</span>
        <button class="btn btn-xs" style="background:var(--amber);color:#111;" onclick="switchTab('conflicts')">View queue</button>
       </div>`
    : `<div style="padding:10px 14px;background:var(--emerald-bg);border:1px solid var(--emerald-border);border-radius:var(--radius-sm);">
        <span class="text-sm" style="color:var(--emerald);">${SVG.check} No open conflicts</span>
       </div>`;

  el.innerHTML = `
    <div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:16px;margin-bottom:22px;">
      <div>
        <div class="health-badge health-${esc(level)}">
          <span class="health-dot"></span>${esc(d.health?.level || "Unknown")}
        </div>
        ${d.health?.reasons?.length
          ? `<ul style="margin:10px 0 0 6px;font-size:.875rem;">${reasons}</ul>`
          : `<p class="text-sm text-muted" style="margin-top:8px;">No issues detected.</p>`}
      </div>
      <div class="text-sm text-faint mono" style="text-align:right;line-height:1.7;">
        ${esc(d.freshness_line || "")}<br>
        As of ${esc(d.as_of || "")}
      </div>
    </div>

    <div class="stat-grid">${tiles}</div>

    <div class="two-col">
      <div>
        <div class="section-heading">At-risk tasks</div>
        <div class="card">
          <div class="tbl-wrap">
            <table><thead><tr><th>ID</th><th>Due</th><th>Reason</th></tr></thead>
            <tbody>${atRiskRows}</tbody></table>
          </div>
        </div>

        <div class="section-heading">Blocked tasks</div>
        <div class="card">
          <div class="tbl-wrap">
            <table><thead><tr><th>ID</th><th>Name</th><th>Due</th><th>Assignee</th></tr></thead>
            <tbody>${blockedRows}</tbody></table>
          </div>
        </div>
      </div>

      <div>
        <div class="section-heading">Upcoming milestones (next 14 days)</div>
        <div class="card">
          <div class="tbl-wrap">
            <table><thead><tr><th>Milestone</th><th>Due</th><th>Phase</th></tr></thead>
            <tbody>${msRows}</tbody></table>
          </div>
        </div>

        <div class="section-heading">Conflicts</div>
        ${confEl}

        <div class="section-heading">Workload</div>
        <div class="card">
          <div class="card-body-sm" style="border-bottom:1px solid var(--border2);">
            <span class="text-xs text-faint">Mira does not rate individuals. Counts and due dates only.</span>
          </div>
          <div class="tbl-wrap">
            <table><thead><tr><th>Person</th><th>Total</th><th>Open</th><th>By status</th></tr></thead>
            <tbody>${wlRows}</tbody></table>
          </div>
        </div>
      </div>
    </div>

    <div class="section-heading">Assumptions</div>
    <div class="card">
      <div class="card-body">
        <ul style="margin-left:16px;font-size:.875rem;line-height:1.8;color:var(--text2);">
          ${(d.assumptions || []).map(a => `<li>${esc(a)}</li>`).join("")}
        </ul>
      </div>
    </div>
  `;
}

// ---------- SCREEN D: Run History ----------

async function loadRuns() {
  const el = document.getElementById("runs-table-wrap");
  el.innerHTML = `<div class="state-box"><span class="spinner"></span><span>Loading...</span></div>`;
  document.getElementById("trace-panel").style.display = "none";
  try {
    const data = await get("/api/runs?limit=100");
    allRuns = data.runs || [];
    renderRunsTable(allRuns);
  } catch (err) {
    el.innerHTML = `<div class="card-body"><div class="error-box">${SVG.x} ${esc(err.message)}</div></div>`;
  }
}

function renderRunsTable(runs) {
  const el = document.getElementById("runs-table-wrap");
  if (runs.length === 0) {
    el.innerHTML = `<div class="state-box">${SVG.clock}<span>No runs yet. Use Ask Mira to create one.</span></div>`;
    return;
  }
  const rows = runs.map(r => `
    <tr class="clickable" onclick="loadTrace('${esc(r.trace_id)}', this)">
      <td class="mono text-sm" style="color:var(--text2);white-space:nowrap;">${esc((r.ts||"").slice(0,19).replace("T"," "))}</td>
      <td style="max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:.875rem;">${esc(r.request||"")}</td>
      <td class="text-sm text-muted">${esc(r.audience||"")}</td>
      <td class="mono text-sm text-muted">${esc(r.model||"")}</td>
      <td>${chipHtml(r.status)}</td>
      <td class="mono text-sm text-muted">${r.usage?.prompt_tokens != null ? r.usage.prompt_tokens + " in" : ""}</td>
      <td class="mono text-sm text-muted">$${(r.usage?.cost_usd ?? 0).toFixed(6)}</td>
      <td class="mono text-sm" style="color:var(--text3);" title="${esc(r.trace_id||"")}">${esc((r.trace_id||"").slice(0,10))}...</td>
    </tr>`).join("");

  el.innerHTML = `<div class="tbl-wrap"><table>
    <thead><tr>
      <th>Time</th><th>Request</th><th>Audience</th><th>Model</th><th>Status</th><th>Tokens</th><th>Cost</th><th>Trace</th>
    </tr></thead>
    <tbody>${rows}</tbody>
  </table></div>`;
}

async function loadTrace(traceId, row) {
  document.querySelectorAll("#runs-table-wrap tbody tr").forEach(r => r.classList.remove("row-active"));
  if (row) row.classList.add("row-active");

  const panel = document.getElementById("trace-panel");
  panel.style.display = "block";
  panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
  panel.innerHTML = `<div class="state-box"><span class="spinner"></span><span>Loading spans...</span></div>`;

  try {
    const data = await get(`/api/traces/${encodeURIComponent(traceId)}`);
    renderTrace(data, traceId);
  } catch (err) {
    panel.innerHTML = `<div class="error-box">${SVG.x} ${esc(err.message)}</div>`;
  }
}

function renderTrace(data, traceId) {
  const spans = data.spans || [];
  const langfuseHost = config.langfuse_host || "";
  const langfuseLink = langfuseHost
    ? `<a href="${esc(langfuseHost)}/trace/${esc(traceId)}" target="_blank" rel="noopener" class="btn btn-secondary btn-sm">${SVG.external} Open in Langfuse</a>`
    : "";

  const steps = spans.map((s, i) => {
    const outSummary = s.output
      ? (typeof s.output === "object"
          ? Object.entries(s.output).slice(0,3).map(([k,v]) => `${esc(k)}: ${esc(String(v).slice(0,60))}`).join(", ")
          : esc(String(s.output).slice(0,120)))
      : "";
    return `<div class="pipeline-step">
      <div class="pipeline-dot pipeline-dot-active">${i+1}</div>
      <div style="flex:1;min-width:0;">
        <div style="display:flex;align-items:center;gap:10px;">
          <span class="pipeline-step-name">${esc(s.name)}</span>
          <span class="pipeline-step-ms">${s.ms ?? 0} ms</span>
        </div>
        ${outSummary ? `<div class="pipeline-step-summary">${outSummary}</div>` : ""}
      </div>
    </div>`;
  }).join("") || `<div class="state-box" style="padding:20px;">No spans for this trace.</div>`;

  const panel = document.getElementById("trace-panel");
  panel.innerHTML = `<div class="card">
    <div class="card-header">
      <span class="card-title">${SVG.clock} Trace spans</span>
      <span style="display:flex;align-items:center;gap:8px;">
        <button class="mono text-xs" style="color:var(--text3);background:none;border:none;cursor:pointer;padding:0;"
                onclick="navigator.clipboard.writeText('${esc(traceId)}').then(()=>toast('Copied.'))"
                title="Click to copy">${esc(traceId)}</button>
        <button class="btn btn-secondary btn-xs" onclick="navigator.clipboard.writeText('${esc(traceId)}').then(()=>toast('Copied.'))">
          ${SVG.copy}
        </button>
        ${langfuseLink}
      </span>
    </div>
    <div class="card-body"><div class="pipeline">${steps}</div></div>
  </div>`;
}

// ---------- conflict badge ----------

async function updateConflictBadge() {
  try {
    const data = await get(`/api/conflicts?as_of=${encodeURIComponent(config.default_as_of || "")}`);
    const open = (data.conflicts || []).filter(c => c.status !== "resolved").length;
    const badge = document.getElementById("nav-conflict-badge");
    if (badge) {
      badge.textContent = open;
      badge.style.display = open > 0 ? "inline-flex" : "none";
    }
  } catch { /* silent */ }
}

// ---------- init ----------

async function init() {
  try {
    config = await get("/api/config");
  } catch {
    config = { default_as_of: "2026-04-20", models: ["mock"], has_openai_key: false, langfuse_host: "" };
  }

  const asofInput = document.getElementById("ask-asof");
  if (asofInput) asofInput.value = config.default_as_of || "";

  const modelSel = document.getElementById("ask-model");
  if (modelSel) {
    modelSel.innerHTML = "";
    (config.models || ["mock"]).forEach(m => {
      const opt = document.createElement("option");
      opt.value = m;
      opt.textContent = m === "mock" ? "mock (no key needed)"
        : (!config.has_openai_key ? `${m} (key not set)` : m);
      modelSel.appendChild(opt);
    });
  }

  document.querySelectorAll(".nav-item[data-tab]").forEach(btn => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  document.getElementById("ask-usetoday")?.addEventListener("change", function() {
    const inp = document.getElementById("ask-asof");
    if (inp) inp.disabled = this.checked;
  });

  document.getElementById("ask-submit")?.addEventListener("click", submitAsk);
  document.getElementById("ask-request")?.addEventListener("keydown", e => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) submitAsk();
  });

  document.querySelectorAll(".qp").forEach(btn => {
    btn.addEventListener("click", () => {
      const req = document.getElementById("ask-request");
      if (req) req.value = btn.dataset.prompt;
      req?.focus();
    });
  });

  updateConflictBadge();
  switchTab("ask");
}

document.addEventListener("DOMContentLoaded", init);
