"use strict";

/* Runway v1 site spine (Increment 3): fetch -> shortlist -> select -> prompt-gen.
 *
 * Static only. No backend, no database, no Runway-side LLM call, no user-file
 * read: the résumé is textarea text held in this page's memory and filled into
 * the prompt the user copies — there is no server for it to go to.
 *
 * Every data-derived value reaches the DOM via textContent / value, never
 * innerHTML — the v0 M13 escaping lesson, carried forward before Increment 4
 * extends it to the pasted LLM result.
 */

const DATA_URL = "data/design.json";
// Build-written mirror of the repo's prompts/recommendations.md (single source,
// D5): the server root is web/, so the repo-root original is unreachable from
// here. scripts/run.py rewrites the mirror on every build (dec. #35).
const TEMPLATE_URL = "prompts/recommendations.md";

// {{SELECTED_ROWS}} uses exactly the design.csv columns, in design.csv order,
// so the prompt's rows match the public download byte-for-word (dec. #36).
const CSV_COLUMNS = [
  "employer", "employer_display", "filing_count", "quarters_present",
  "quarters", "repeat_sponsor", "soc_codes", "soc_titles",
  "worksite_states", "worksite_cities",
  "wage_annual_min", "wage_annual_median", "wage_annual_max",
];

const TOKENS = ["{{SELECTED_ROWS}}", "{{PORTFOLIO}}", "{{RESUME_OR_NONE}}"];

const state = {
  data: null,          // parsed design.json (null until a role is loaded)
  template: null,      // fetched prompt template, cached after first success
  selected: new Set(), // `employer` keys — the aggregation key, unique per row
  resumeText: "",
};

const $ = (id) => document.getElementById(id);
const fmt = (n) => Number(n).toLocaleString("en-US");

/* ---------------------------------------------------------------- load */

function setLoadState(mode, message) {
  // mode: "idle" | "loading" | "error"
  $("load-status").hidden = mode !== "loading";
  if (mode === "loading") $("load-status").textContent = "Loading the shortlist…";
  $("load-error").hidden = mode !== "error";
  if (mode === "error") $("load-error-message").textContent = message;
}

async function loadShortlist() {
  setLoadState("loading");
  try {
    const res = await fetch(DATA_URL, { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status} for ${DATA_URL}`);
    const data = await res.json();
    if (!Array.isArray(data.employers) || !Array.isArray(data.caveats)) {
      throw new Error(`${DATA_URL} is missing employers[]/caveats[]`);
    }
    state.data = data;
    state.selected.clear();
    renderShortlist(data);
    setLoadState("idle");
    for (const id of ["section-inputs", "section-shortlist", "section-prompt"]) {
      $(id).hidden = false;
    }
    updatePromptGate();
  } catch (err) {
    // Plain-English failure, never a stack trace or a blank page.
    console.error(err);
    setLoadState("error", "Couldn't load the shortlist. Retry, or check that web/data/design.json exists.");
  }
}

/* ----------------------------------------------------------- shortlist */

function renderShortlist(data) {
  // Caveats: VERBATIM from the fetched JSON — the single source is the engine's
  // _util.CAVEATS, emitted into design.json; nothing is hardcoded here (§7).
  const list = $("caveats-list");
  list.replaceChildren();
  for (const caveat of data.caveats) {
    const li = document.createElement("li");
    li.textContent = caveat;
    list.appendChild(li);
  }

  // Repeat-sponsor needs filings in >= 2 fiscal years; with a single-FY window
  // the column cannot fire, so say so instead of showing a silently-empty column.
  const fiscalYears = [...new Set((data.quarters_used || []).map((q) => String(q).slice(0, 6)))];
  const note = $("single-quarter-note");
  note.hidden = fiscalYears.length >= 2;
  if (fiscalYears.length < 2) {
    note.textContent =
      `Note: this shortlist covers a single fiscal year (${fiscalYears.join(", ") || "one quarter"}). ` +
      "The Repeat column needs filings in at least two fiscal years, so it stays empty until more data lands.";
  }

  const body = $("shortlist-body");
  body.replaceChildren();
  for (const employer of data.employers) body.appendChild(renderRow(employer));

  renderFunnelLine(data);

  const prov = $("provenance-line");
  prov.replaceChildren();
  prov.append(`Source: ${data.source} · generated ${data.generated_at_utc} · `);
  const provLink = document.createElement("a");
  provLink.href = "data/design.provenance.json";
  provLink.textContent = "provenance";
  const csvLink = document.createElement("a");
  csvLink.href = "data/design.csv";
  csvLink.textContent = "download the shortlist (CSV)";
  prov.append(provLink, " · ", csvLink);
}

function renderRow(employer) {
  const tr = document.createElement("tr");

  const tdSelect = document.createElement("td");
  tdSelect.className = "center";
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.setAttribute("aria-label", `target ${employer.employer_display}`);
  checkbox.addEventListener("change", () => {
    if (checkbox.checked) state.selected.add(employer.employer);
    else state.selected.delete(employer.employer);
    tr.classList.toggle("selected", checkbox.checked);
    updatePromptGate();
  });
  tdSelect.appendChild(checkbox);

  // D8: the company name links to a Google search for "<name> careers" — the
  // fastest honest way to check hiring yourself; Runway asserts nothing about
  // openings. URL-encoded, so a hostile employer_display cannot break the href.
  const tdName = document.createElement("td");
  const link = document.createElement("a");
  link.href = "https://www.google.com/search?q=" +
    encodeURIComponent(`${employer.employer_display} careers`);
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = employer.employer_display;
  tdName.appendChild(link);

  const tdFilings = document.createElement("td");
  tdFilings.className = "num";
  tdFilings.textContent = fmt(employer.filing_count);

  const tdQuarters = document.createElement("td");
  tdQuarters.textContent = employer.quarters;

  const tdRepeat = document.createElement("td");
  tdRepeat.className = "center";
  tdRepeat.textContent = employer.repeat_sponsor === "yes" ? "✓" : "";

  const tdSoc = document.createElement("td");
  tdSoc.textContent = employer.soc_titles;

  const tdStates = document.createElement("td");
  tdStates.textContent = employer.worksite_states;

  // A wage excluded from the stats is JSON null (never "nan", v0 F5) and
  // renders as an em dash — absent, not zero (dec. #37).
  const tdWage = document.createElement("td");
  tdWage.className = "num";
  tdWage.textContent =
    employer.wage_annual_median == null ? "—" : `$${fmt(employer.wage_annual_median)}`;

  tr.append(tdSelect, tdName, tdFilings, tdQuarters, tdRepeat, tdSoc, tdStates, tdWage);
  return tr;
}

function renderFunnelLine(data) {
  // Honest numbers: the funnel values come from the fetched JSON, and the final
  // employer count is the rows actually rendered (employers.length), never a
  // separate literal that could go stale.
  const f = data.funnel;
  const wageLevel = data.filters && data.filters.pw_wage_level;
  $("funnel-line").textContent =
    `${(data.quarters_used || []).join(" + ")}: ${fmt(f.rows_total)} filings in the raw data` +
    ` → ${fmt(f.rows_certified)} certified` +
    ` → ${fmt(f.rows_soc_matched)} in the design SOC codes` +
    ` → ${fmt(f.rows_selected)} at entry wage (Level ${wageLevel})` +
    ` → ${fmt(data.employers.length)} employers after grouping.`;
}

/* ------------------------------------------------------------- inputs */

function portfolioUrl() {
  // "Validated as a URL": the URL constructor must accept it and the scheme
  // must be http(s) — nothing else belongs in a portfolio link (dec. #38).
  // No silent rewriting: what the user typed is what enters the prompt.
  const raw = $("portfolio-input").value.trim();
  if (!raw) return null;
  try {
    const url = new URL(raw);
    return url.protocol === "https:" || url.protocol === "http:" ? raw : null;
  } catch {
    return null;
  }
}

function updateResumeState() {
  state.resumeText = $("resume-input").value;
  const trimmed = state.resumeText.trim();
  $("resume-state").textContent = trimmed
    ? `Résumé attached — ${fmt(trimmed.length)} characters, held only in this browser.`
    : "No résumé attached.";
}

/* --------------------------------------------------------- prompt-gen */

function updatePromptGate() {
  // PromptReady = >=1 company selected AND a valid portfolio URL present.
  const portfolio = portfolioUrl();
  const raw = $("portfolio-input").value.trim();
  $("portfolio-hint").hidden = !raw || portfolio !== null;

  const missing = [];
  if (state.selected.size === 0) missing.push("select at least one company in the table");
  if (portfolio === null) missing.push("add your portfolio link (https://…)");

  $("generate-btn").disabled = missing.length > 0;
  $("prompt-gate-hint").textContent = missing.length
    ? `To generate: ${missing.join(" · ")}.`
    : `Ready — ${state.selected.size} ${state.selected.size === 1 ? "company" : "companies"} selected.`;

  // Any change makes an already-shown prompt stale: hide it rather than let a
  // prompt that no longer matches the inputs get copied.
  if (!$("prompt-box").hidden) {
    $("prompt-box").hidden = true;
    showPromptStatus("Inputs changed since the last prompt — generate again.", false);
  }
}

function showPromptStatus(message, isError) {
  const status = $("prompt-status");
  status.hidden = !message;
  status.textContent = message || "";
  status.classList.toggle("error", Boolean(isError));
}

function csvField(value) {
  // RFC 4180: quote a field containing comma, quote, or newline; double the
  // quotes inside. null (excluded wage) becomes an empty cell, as in design.csv.
  if (value == null) return "";
  const s = String(value);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function buildSelectedRowsCsv() {
  const rows = state.data.employers.filter((e) => state.selected.has(e.employer));
  const lines = [CSV_COLUMNS.join(",")];
  for (const row of rows) {
    lines.push(CSV_COLUMNS.map((col) => csvField(row[col])).join(","));
  }
  return lines.join("\n");
}

async function generatePrompt() {
  // Snapshot the inputs at click time: the template fetch below is async, and
  // the prompt must reflect what the user saw when they clicked, not edits
  // made while the fetch was in flight.
  const portfolio = portfolioUrl();
  const selectedRowsCsv = buildSelectedRowsCsv();
  const resume = state.resumeText.trim();
  if (portfolio === null || state.selected.size === 0) return;

  showPromptStatus("Fetching the prompt template…", false);
  try {
    if (state.template === null) {
      const res = await fetch(TEMPLATE_URL, { cache: "no-cache" });
      if (!res.ok) throw new Error(`HTTP ${res.status} for ${TEMPLATE_URL}`);
      const template = await res.text();
      const absent = TOKENS.filter((t) => !template.includes(t));
      if (absent.length) {
        throw new Error(`template is missing ${absent.join(", ")} — re-run scripts/run.py`);
      }
      state.template = template;
    }

    // split/join, not replace(): the résumé may legitimately contain `$&`-style
    // sequences that String.replace would treat as substitution patterns.
    const filled = state.template
      .split("{{SELECTED_ROWS}}").join(selectedRowsCsv)
      .split("{{PORTFOLIO}}").join(portfolio)
      .split("{{RESUME_OR_NONE}}").join(resume || "none provided");

    $("prompt-output").value = filled;
    $("prompt-box").hidden = false;
    resetCopyButton();
    showPromptStatus("", false);
    $("prompt-output").scrollTop = 0;
  } catch (err) {
    console.error(err);
    showPromptStatus(
      "Couldn't load the prompt template. Retry — and if this keeps failing, " +
      "check that web/prompts/recommendations.md exists (scripts/run.py writes it).",
      true,
    );
  }
}

let copyResetTimer = null;

function resetCopyButton() {
  clearTimeout(copyResetTimer);
  $("copy-btn").textContent = "Copy prompt";
}

async function copyPrompt() {
  const output = $("prompt-output");
  try {
    await navigator.clipboard.writeText(output.value);
  } catch {
    // Clipboard API needs a secure context; localhost qualifies, plain LAN
    // hosts may not — fall back to select + execCommand there.
    output.focus();
    output.select();
    document.execCommand("copy");
  }
  $("copy-btn").textContent = "Copied ✓";
  clearTimeout(copyResetTimer);
  copyResetTimer = setTimeout(resetCopyButton, 2000);
}

/* --------------------------------------------------------------- wire */

$("title-select").addEventListener("change", (event) => {
  if (event.target.value === "design") loadShortlist();
});
$("retry-btn").addEventListener("click", loadShortlist);
$("portfolio-input").addEventListener("input", updatePromptGate);
$("resume-input").addEventListener("input", () => {
  updateResumeState();
  updatePromptGate();
});
$("generate-btn").addEventListener("click", generatePrompt);
$("copy-btn").addEventListener("click", copyPrompt);
