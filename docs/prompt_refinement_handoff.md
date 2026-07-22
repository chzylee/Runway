# Prompt refinement — data & inputs handoff

**Purpose.** Everything a fresh session needs to refine `prompts/recommendations.md`
(the reviewer prompt the user runs in their own LLM) without re-deriving it from the
code. **Disposable working brief** — regenerate after any data-shape or schema change.
Captured 2026-07-21 against a real 2-quarter `design` pull (FY2025Q4 + FY2026Q1).

> The owner has flagged that **the report output schema may change** — treat §3 as the
> current contract to *improve*, not a fixed target.

---

## TL;DR for the refiner

1. The prompt sees **only three things**: a portfolio string, a résumé *path* string, and
   a CSV of the employer rows the user checkboxed. That CSV is 13 columns per row (§1).
2. **The biggest lever:** a rich aggregate `patterns` object (recurring title tokens,
   O*NET occupation mix, in-house vs staffing, industry sectors) and the funnel counts are
   **computed, emitted to JSON, and shown in the UI — but NOT fed to the prompt** (§2).
   That whole signal layer is sitting on the table unused. Deciding whether/how to pipe it
   in is probably the highest-value refinement.
3. If you change the **output schema** (§3), you are also setting the contract for the
   *not-yet-built* results renderer (Increment 4). Land the schema here first.
4. Some things are **locked** (§4): the 5-caveat block is byte-checked against the engine,
   the 3 fill-tokens are name-checked by the site, and "companies only from the selected
   rows" is the product's integrity rule.

---

## 1. Inputs the prompt actually receives

The site fills three tokens in `prompts/recommendations.md`, then hands the user the
finished text. **The LLM sees nothing else.**

| Token | Filled with | Absent value |
|---|---|---|
| `{{PORTFOLIO}}` | the portfolio URL string | `no portfolio link provided` |
| `{{RESUME_OR_NONE}}` | a résumé **file path** string (the site never reads the file — dec. #40) | `none provided` |
| `{{SELECTED_ROWS}}` | RFC-4180 CSV of the checkboxed employer rows | — (gate requires ≥1 row) |

- At least one of portfolio / résumé is always present (dec. #41), never neither.
- Token strings are **fixed**: `web/app.js` verifies the template still contains all three
  and errors if not — don't rename them.

**`{{SELECTED_ROWS}}` columns** (exactly `design.csv`, in order — dec. #36):

```
employer, employer_display, filing_count, quarters_present, quarters,
repeat_sponsor, soc_codes, soc_titles, worksite_states, worksite_cities,
wage_annual_min, wage_annual_median, wage_annual_max
```

Sample row (as the LLM sees it, one CSV line per selected employer):

```json
{
  "employer": "THE JOY CULTURE FOUNDATION",   // normalized group key
  "employer_display": "THE JOY CULTURE FOUNDATION", // most-common raw spelling
  "filing_count": 2,
  "quarters_present": 2,
  "quarters": "FY2025Q4; FY2026Q1",
  "repeat_sponsor": "yes",                     // present in >=2 quarters (~>=2 fiscal years)
  "soc_codes": "27-1024",
  "soc_titles": "Graphic Designers",
  "worksite_states": "CA",
  "worksite_cities": "Menlo Park",
  "wage_annual_min": 58240,                     // may be null (see §5)
  "wage_annual_median": 63024,
  "wage_annual_max": 67808
}
```

Field meanings, condensed:
- **employer vs employer_display** — the first is the normalized merge key (uppercased,
  `LLC/INC/CORP/LTD` stripped); the second is the human spelling. Normalization is
  conservative → occasionally *under*-merges (a company can appear as two near-duplicate rows).
- **repeat_sponsor / quarters** — the "sponsors *consistently*" signal; "yes" = filed in
  ≥2 quarters, which after cumulative-FYTD supersession means ≥2 fiscal years.
- **wage_annual_{min,median,max}** — annualized from `WAGE_RATE_OF_PAY_FROM`; **can be null**.
- **soc_titles** — official DOL occupation title(s); the UI annotates "Web and Digital
  Interface Designers" as "(UI/UX)" but the data string is untouched.

## 2. Available in the data, NOT currently in the prompt (candidate inputs)

All of this lives in `web/data/<role>.json` and drives the UI, but never reaches the LLM.

**`patterns` object** (dec. #44) — deterministic, **employer-denominated** counts over the
selected rows, with a floor of **3 distinct employers** before anything is stated (one
prolific filer can't manufacture a pattern). Shape (counts from the real `design` pull):

- `basis`: `{ filings: 95, employers: 76, measured_by: "employers", min_support_employers: 3 }`
- `job_titles.recurring_tokens[]`: `{ token, employers, filings }` — e.g. `graphic` (22 emp),
  `product` (14), `industrial` (8), `ux` (5), `senior` (3). Role words (design/designer)
  stripped as zero-signal; seniority + domain words survive.
- `job_titles.distinct_titles[]`: `{ title, employers, filings }` — the raw title spread
  (long tail; see §5 for dirty entries).
- `onet_occupations[]`: `{ soc_code, title, employers, filings }` — the occupation mix,
  keeping the O*NET detail suffix (e.g. `15-1255.01` Video Game Designers stays distinct).
- `placement_model`: `{ in_house: {employers, filings}, third_party_site: {employers, filings} }`
  — from `SECONDARY_ENTITY = "YES"`. Currently lopsided (75 in-house / 1 third-party).
- `industry_naics2[]`: `{ code, label, employers, filings }` — 2-digit Census sector rollup;
  top sector is `54 Professional/Scientific/Technical` (22 emp).

**`funnel`** — `rows_total 201,700 → certified 181,277 → soc_matched 1,116 → selected 95`.
Useful for honesty framing ("95 filings out of 201k"), also unused by the prompt.

**`provenance.json`** — quarters used/superseded, wage units seen, case statuses seen, etc.

## 3. Current report schema the LLM must return — **MAY CHANGE**

From `prompts/recommendations.md` ("Output contract"). Single JSON object; `projects` must
be exactly 3; every `projects[].company` must be one of the selected rows.

```json
{
  "overarching_recommendation": { "thread": "...", "why": "..." },
  "projects": [
    { "title": "...", "company": "...", "gap": "...",
      "evidence": "...", "build": "...", "business_case": "..." }
  ],
  "skills_to_develop": {
    "for_the_already_building": "...",
    "skills": ["...", "..."]
  }
}
```

**Coupling:** this JSON is what the site's paste → validate → escape-render step
(Increment 4, **not built yet**) will consume. Whatever shape you land on becomes that
renderer's contract, so settle the schema here before the renderer is built.

## 4. Locked constraints (don't break these while refining)

- **Caveats block** — the 5 caveats between `<!-- CAVEATS:BEGIN -->` / `END` are byte-for-byte
  checked against `engine/_util.CAVEATS` by `scripts/check_caveats_parity.py` (a build gate).
  Don't reword or reorder them; they're machine-managed.
- **Fill tokens** — keep `{{SELECTED_ROWS}}` / `{{PORTFOLIO}}` / `{{RESUME_OR_NONE}}` verbatim.
- **Integrity rules** — companies only from the selected rows; label anything unsupported
  "assumption"; **no immigration legal advice**; filing counts / wage levels / SOC titles /
  states are *facts*, everything else about a company is *unknown* unless the user's notes say so.

## 5. Data realities to be robust to (from the real pull)

- **Small N** — 76 employers / 95 filings across two quarters. Level-I *design* is a thin slice.
- **Null wages** — a non-`Year` pay unit (e.g. Bi-Weekly) → `wage_annual_*` is null but the
  filing still counts. Don't treat a null wage as "no data about the employer."
- **Dirty titles** — raw `JOB_TITLE` includes encoding artifacts (e.g.
  `"Industrial Designer �g Robotics"`) and non-descriptive junk (`"Studio Staff"`,
  `"Team Leader"`). The tokenizer surfaces these; the prompt should not over-index on any one title.
- **Under-merge** — conservative employer normalization means the same real company can appear
  as two rows (caveat #4).
- **Weak placement signal** — `placement_model` is 75/1 at this scale; not yet meaningful.
- **Unused columns** — `VISA_CLASS` and `WAGE_RATE_OF_PAY_TO` are parsed into the parquet but
  read by nothing (context only, not available to the prompt anyway).

## Pointers

- Prompt (single source): `prompts/recommendations.md` (mirrored to `web/prompts/` at build)
- Emitted data: `web/data/{design,uiux}.json` (+ `.provenance.json`, `.csv`)
- Emit + schema: `scripts/build_shortlist.py`; patterns: `engine/sponsors.py` `compute_patterns` (dec. #44)
- Token fill / CSV assembly: `web/app.js` (`CSV_COLUMNS`, `buildSelectedRowsCsv`, generate handler)
- Future renderer: Increment 4 (not built) — will consume the §3 JSON
