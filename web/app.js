"use strict";

/* Runway v1 site spine (Increment 3): fetch -> shortlist -> select -> prompt-gen.
 *
 * Static only. No backend, no database, no Runway-side LLM call, no user-file
 * read: the résumé input is a FILE PATH STRING (dec. #40), never file content —
 * Runway doesn't open it, doesn't read it, there is no upload and no server for
 * it to go to.
 *
 * Every data-derived value reaches the DOM via textContent / value, never
 * innerHTML — the v0 M13 escaping lesson, carried forward before Increment 4
 * extends it to the pasted LLM result.
 */

// Each registered role (dec. #39) is a sibling data file: data/<role>.json.
// Keep in sync with the <option value="..."> list in index.html.
const ROLE_LABELS = { design: "Design", uiux: "UI/UX Design" };
const KNOWN_ROLES = new Set(Object.keys(ROLE_LABELS));
const dataUrlFor = (role) => `data/${role}.json`;
// Build-written mirror of the repo's prompts/recommendations.md (single source,
// D5): the server root is web/, so the repo-root original is unreachable from
// here. scripts/run.py rewrites the mirror on every build (dec. #35).
const TEMPLATE_URL = "prompts/recommendations.md";

// The official SOC title for what's colloquially called "UI/UX" (dec. #39) —
// annotated in the shortlist table so the DOL wording and the recognizable term
// both read clearly. Display only; the underlying soc_titles data is untouched.
const UIUX_SOC_TITLE = "Web and Digital Interface Designers";

// {{SELECTED_ROWS}} uses exactly the design.csv columns, in design.csv order,
// so the prompt's rows match the public download byte-for-word (dec. #36).
const CSV_COLUMNS = [
  "employer", "employer_display", "filing_count", "quarters_present",
  "quarters", "repeat_sponsor", "soc_codes", "soc_titles",
  "worksite_states", "worksite_cities",
  "wage_annual_min", "wage_annual_median", "wage_annual_max",
];

const TOKENS = ["{{SELECTED_ROWS}}", "{{PORTFOLIO}}", "{{RESUME_OR_NONE}}"];

export const state = {
  role: null,           // the loaded role's value, e.g. "design" | "uiux"
  data: null,           // parsed <role>.json (null until a role is loaded)
  template: null,       // fetched prompt template, cached after first success
  selected: new Set(),  // `employer` keys — the aggregation key, unique per row
  resumePath: "",       // a file path string, never file content (dec. #40)
  sort: { key: null, dir: 1 }, // shortlist table sort: null key = DOL/engine order
};

// Column -> comparable value, for the sortable shortlist table. `filing_count`
// and `wage_annual_median` sort numerically; the rest sort as case-folded text.
// wage_annual_median may be null (excluded from stats, dec. #37) — sortedEmployers
// always pushes null to the end, in either direction, rather than treating it as 0.
const SORT_ACCESSORS = {
  employer_display: (e) => e.employer_display.toLowerCase(),
  filing_count: (e) => e.filing_count,
  quarters: (e) => e.quarters,
  repeat_sponsor: (e) => (e.repeat_sponsor === "yes" ? 1 : 0),
  soc_titles: (e) => e.soc_titles.toLowerCase(),
  worksite_states: (e) => e.worksite_states,
  wage_annual_median: (e) => e.wage_annual_median,
};

function sortedEmployers(employers) {
  const { key, dir } = state.sort;
  if (!key) return employers;
  const accessor = SORT_ACCESSORS[key];
  return [...employers].sort((a, b) => {
    const av = accessor(a);
    const bv = accessor(b);
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    if (av < bv) return -dir;
    if (av > bv) return dir;
    return 0;
  });
}

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

async function loadShortlist(role) {
  state.role = role;
  const dataUrl = dataUrlFor(role);
  setLoadState("loading");
  try {
    const res = await fetch(dataUrl, { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status} for ${dataUrl}`);
    const data = await res.json();
    if (!Array.isArray(data.employers) || !Array.isArray(data.caveats)) {
      throw new Error(`${dataUrl} is missing employers[]/caveats[]`);
    }
    state.data = data;
    state.selected.clear();
    state.sort = { key: null, dir: 1 };
    updateSortIndicators();
    renderShortlist(data);
    setLoadState("idle");
    for (const id of ["section-inputs", "section-shortlist", "section-prompt"]) {
      $(id).hidden = false;
    }
    updatePromptGate();
  } catch (err) {
    // Plain-English failure, never a stack trace or a blank page.
    console.error(err);
    setLoadState("error", `Couldn't load the shortlist. Retry, or check that web/${dataUrl} exists.`);
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

  renderTableBody(data.employers);
  renderFunnelLine(data);

  const prov = $("provenance-line");
  prov.replaceChildren();
  prov.append(`Source: ${data.source} · generated ${data.generated_at_utc} · `);
  const provLink = document.createElement("a");
  provLink.href = `data/${state.role}.provenance.json`;
  provLink.textContent = "provenance";
  const csvLink = document.createElement("a");
  csvLink.href = `data/${state.role}.csv`;
  csvLink.textContent = "download the shortlist (CSV)";
  prov.append(provLink, " · ", csvLink);
}

function renderTableBody(employers) {
  // Re-run on every sort click (state.data.employers itself is never reordered)
  // as well as on a fresh load — either way, selection is keyed by `employer`
  // (renderRow reads state.selected), so re-sorting never drops a checked row.
  const body = $("shortlist-body");
  body.replaceChildren();
  for (const employer of sortedEmployers(employers)) body.appendChild(renderRow(employer));
}

export function renderRow(employer) {
  const tr = document.createElement("tr");
  const isSelected = state.selected.has(employer.employer);
  tr.classList.toggle("selected", isSelected);

  const tdSelect = document.createElement("td");
  tdSelect.className = "center";
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = isSelected;
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

  // Annotate the recognizable "UI/UX" term next to its official SOC title
  // (dec. #39) — display only, employer.soc_titles itself stays DOL-verbatim.
  const tdSoc = document.createElement("td");
  tdSoc.textContent = employer.soc_titles.includes(UIUX_SOC_TITLE)
    ? `${employer.soc_titles} (UI/UX)`
    : employer.soc_titles;

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
    ` → ${fmt(f.rows_soc_matched)} in the ${ROLE_LABELS[data.role] || data.role} SOC codes` +
    ` → ${fmt(f.rows_selected)} at entry wage (Level ${wageLevel})` +
    ` → ${fmt(data.employers.length)} employers after grouping.`;
}

function setSort(key) {
  if (!state.data) return;
  state.sort = state.sort.key === key
    ? { key, dir: -state.sort.dir }
    : { key, dir: 1 };
  updateSortIndicators();
  renderTableBody(state.data.employers);
}

function updateSortIndicators() {
  for (const th of document.querySelectorAll("#shortlist-table th[data-sort-key]")) {
    const active = th.dataset.sortKey === state.sort.key;
    th.classList.toggle("sorted-asc", active && state.sort.dir === 1);
    th.classList.toggle("sorted-desc", active && state.sort.dir === -1);
  }
}

/* ------------------------------------------------------------- inputs */

// "Validated as a URL": the URL constructor must accept it and the scheme must
// be http(s) — nothing else belongs in a portfolio link (dec. #38). Rejects
// javascript:/data:/bare-domain-no-scheme values; a security-relevant check
// (dec. #42), not just a format nicety, since this value ends up in an <a>-free
// context (plain text in the copied prompt) but is exactly the kind of input
// validation worth pinning against regression.
export function isValidPortfolioUrl(raw) {
  if (!raw) return false;
  try {
    const url = new URL(raw);
    return url.protocol === "https:" || url.protocol === "http:";
  } catch {
    return false;
  }
}

function portfolioUrl() {
  // No silent rewriting: what the user typed is what enters the prompt.
  const raw = $("portfolio-input").value.trim();
  return isValidPortfolioUrl(raw) ? raw : null;
}

function updateResumeState() {
  state.resumePath = $("resume-input").value;
  const trimmed = state.resumePath.trim();
  $("resume-state").textContent = trimmed
    ? `Résumé path noted: ${trimmed}`
    : "No résumé path provided.";
}

/* --------------------------------------------------------- prompt-gen */

// Pure branch logic for the PromptReady gate (dec. #41), decoupled from the DOM
// so it's directly unit-testable — >= 1 company selected AND (a valid portfolio
// URL OR a résumé path). Neither input is required alone, but at least one
// must be present; a non-empty, invalid portfolio value still blocks (that's a
// typo to fix, not a missing-input case) rather than silently falling through
// to "use the résumé instead."
export function computePromptGate({ portfolioRaw, portfolioValid, resumePath, selectedCount }) {
  const portfolioInvalid = portfolioRaw !== "" && !portfolioValid;
  const missing = [];
  if (selectedCount === 0) missing.push("select at least one company in the table");
  if (portfolioInvalid) {
    missing.push("fix your portfolio link (https://…)");
  } else if (!portfolioValid && !resumePath) {
    missing.push("add a portfolio link or a résumé path — at least one");
  }
  return { missing, portfolioInvalid };
}

function updatePromptGate() {
  const portfolioRaw = $("portfolio-input").value.trim();
  const resumePath = $("resume-input").value.trim();
  const { missing, portfolioInvalid } = computePromptGate({
    portfolioRaw,
    portfolioValid: isValidPortfolioUrl(portfolioRaw),
    resumePath,
    selectedCount: state.selected.size,
  });
  $("portfolio-hint").hidden = !portfolioInvalid;

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
  const resumePath = state.resumePath.trim();
  if ((portfolio === null && !resumePath) || state.selected.size === 0) return;

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

    // split/join, not replace(): a path or the CSV rows could legitimately
    // contain `$&`-style sequences that String.replace would treat as
    // substitution patterns.
    const filled = state.template
      .split("{{SELECTED_ROWS}}").join(selectedRowsCsv)
      .split("{{PORTFOLIO}}").join(portfolio || "no portfolio link provided")
      .split("{{RESUME_OR_NONE}}").join(resumePath || "none provided");

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

// Guarded so this module can be imported in a test environment that doesn't
// load the full index.html DOM (the vitest suite imports pure/DOM-fragment
// functions like renderRow/computePromptGate directly, not the whole page).
// On the real served page #title-select always exists, so this is always true.
if ($("title-select")) {
  $("title-select").addEventListener("change", (event) => {
    const role = event.target.value;
    $("find-btn").disabled = !KNOWN_ROLES.has(role);
    // The dropdown moved off the role the visible sections were built for —
    // hide them again rather than leave a shortlist on screen that no longer
    // matches the selector; "Find sponsoring companies" is what shows it again.
    if (state.role !== null && role !== state.role) {
      for (const id of ["section-inputs", "section-shortlist", "section-prompt"]) {
        $(id).hidden = true;
      }
      setLoadState("idle");
    }
  });
  $("find-btn").addEventListener("click", () => {
    const role = $("title-select").value;
    if (KNOWN_ROLES.has(role)) loadShortlist(role);
  });
  $("retry-btn").addEventListener("click", () => loadShortlist(state.role));
  $("portfolio-input").addEventListener("input", updatePromptGate);
  $("resume-input").addEventListener("input", () => {
    updateResumeState();
    updatePromptGate();
  });
  $("generate-btn").addEventListener("click", generatePrompt);
  $("copy-btn").addEventListener("click", copyPrompt);

  for (const th of document.querySelectorAll("#shortlist-table th[data-sort-key]")) {
    th.addEventListener("click", () => setSort(th.dataset.sortKey));
    th.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        setSort(th.dataset.sortKey);
      }
    });
  }
}
