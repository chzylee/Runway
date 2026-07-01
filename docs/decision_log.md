# Stay Here — Decision Log (FDE proof / Judgment Ledger)

The forks and why. This is the job-search proof, not the report. Each entry: the
choice, the alternative rejected, and the reasoning. Doubles as the
build-in-public reasoning trail (public — contains no personal data).

---

## Decisions inherited from the brief (carried, with the why)

| # | Fork | Chose | Over | Why |
|---|------|-------|------|-----|
| 1 | What the product *is* | Advisory diagnostic — named-company gap-read | Another directory | h1bgrader/MyVisaJobs/h1bdata already list *who sponsors*. None tell a person what to *do*. The advice is the gap. |
| 2 | New-grad signal | `PW_WAGE_LEVEL = I` (entry-wage filings) | Salary thresholds | Wage *level* is the mandated, comparable entry-tier marker; salary is noisy across metros/roles. Salary kept as a secondary display only. |
| 3 | Data source | Raw DOL OFLC **LCA** disclosure file | A directory's pre-chewed view, or PERM/prevailing-wage | Grounding is the moat. Raw filings let us filter to entry-wage *design* ourselves. LCA (temporary, H-1B) is the sponsorship-intent signal; PERM is green-card stage, wrong layer. |
| 4 | ICP | The new-grad **designer** (n=1, works on Rally) | The cousin's post-lottery need | One real user, finishable by hand. Cousin's tool is a separate, parked build (different legal surface). |
| 5 | Where AI is allowed | Judgment step only (gap-read), human-reviewed | AI in the data step | The data step must be deterministic and traceable. AI on the deterministic parse would inject ungrounded error into the moat. |
| 6 | Architecture | **Engine/altitude split** — `build_sponsor_table()` is a reusable, role-parameterized function; report is a thin caller | One monolithic notebook | The Level-I parse IS the engine the future self-serve UI calls. Keeping it separable is one of the two allowed forward-compat choices. |
| 7 | Role generality | `ROLE_SOC` dict, seeded design-only | Hardcoded design SOCs | Adding "consultant" later = one dict entry. The second allowed forward-compat choice. Multi-role *judgment* (OPT caveats per role) stays v2. |
| 8 | **Layer A (OPT-now postings pipeline)** | **Cut to v2** | Build it in v1 | The finishing-discipline call. Least grounded, most fragile (regex/LLM work-auth classification), least productizable — doesn't survive into a self-serve product. v1 replaces it with a manual "are they hiring now" eyeball + one caveat. Building it would be the finish-failure trap. |

---

## Decisions made *during* the build (mine; reviewed)

| # | Fork | Chose | Over | Why |
|---|------|-------|------|-----|
| B1 | **Kill-test first** | Ran `build_sponsor_table(design, "I", FY2025Q4)` before anything else | Build the repo, then check | The brief's go/no-go gate. One quarter → **52 distinct real companies, not staffing-dominated** (top employer 7 filings; Amazon/Deloitte/Activision/DraftKings/Esri present). Door is open → GO. |
| B2 | Quarter coverage | **Full FY2025 (Q1–Q4)** for the shortlist | Single quarter (brief's literal scope) | "*Actually* sponsors entry-wage designers" is far stronger when a company appears across multiple quarters. The engine is parameterized for exactly this, so it's a one-call extension, not new scope. Single quarter remains the documented kill-test. |
| B3 | Quarter vintage | **FY2025** (most recent complete fiscal year) | Older 2021+ quarter | Brief says "use a 2021+ quarter." Most recent = most relevant to her job search. Confirmed `PW_WAGE_LEVEL` is the bare-`"I"` spelling in this vintage (not "Level I"/1). |
| B4 | Column access | Resolve by **name** from each file's header | Hardcoded column indices | Columns are reordered across quarters (FY2025 Q1 has `WORKSITE_COUNTY` where Q4 has `WORKSITE_CITY`). The verification assert *caught* the index bug mid-build — exactly its job. Name resolution is robust. |
| B5 | "Notebook" form | **Module + thin runner script** (`scripts/build_shortlist.py`) | A Jupyter notebook | Same provenance + verification "cells," but diffable, reviewable, and a cleaner realization of the engine/altitude split. The success criterion "every cell traces to source + quarter" is met by the script's printed provenance. |
| B6 | Privacy split | Her HTML report → `output/private/` (gitignored); engine + method + decision log + (public-record) shortlist CSV → public | Publish everything / publish nothing | Her portfolio + job-search data must never be published. LCA employer names are public record, so the shortlist itself is shareable. |
| B7 | Report format | Self-contained HTML, embedded CSS, no JS/pandoc | pandoc/PDF pipeline | pandoc isn't installed; a single self-contained HTML opens anywhere and is trivially shareable for early UX feedback. PDF stays optional. |

---

## Known limits (named, not hidden)

- **LCA ≠ hire-now.** Certified filing = ability/intent to sponsor, not a current
  req. v1 covers this with a manual hiring eyeball + an explicit report caveat.
- **Design likely not STEM-OPT** → ~12-mo OPT runway. Stated in the report.
- **Employer normalization is conservative** (uppercase, strip LLC/INC/CORP/LTD,
  punctuation). It will not merge genuinely different legal spellings of the same
  parent (e.g. distinct subsidiaries). Over-merging is the worse error, so we
  under-merge on purpose.
- **One role (design), one fiscal year.** Multi-role and live refresh are v2.

## Artifacts

- Engine: `engine/sponsors.py` · Verification: `engine/verify.py`
- Runners: `scripts/convert_quarters.py`, `scripts/build_shortlist.py`, `scripts/build_report.py`
- Saved gap-read prompt: `prompts/gap_read.md`
- Public shortlist: `output/sponsors_levelI.csv` · Her report (private): `output/private/stay_here_report.html`
