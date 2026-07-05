# Runway

A sponsorship diagnostic for international new-grad designers. It answers two
questions with data instead of folklore:

1. **Who actually sponsors entry-level designers?** — a shortlist of companies
   with *certified, entry-wage (Level I)* design visa filings, built from raw
   US Department of Labor LCA disclosure data.
2. **What should I build to be worth a visa to them?** — a human-reviewed
   "gap read" naming the 3 portfolio projects aimed at specific companies from
   that shortlist.

The edge is data-grounding plus judgment, not a directory: every number in the
output traces back to a public DOL filing, and the advice layer is written by
a human reviewer, never by a script.

## How it works

- **Layer 1 — deterministic engine (no LLM).** `engine/` filters DOL LCA data
  to certified Level-I design filings and aggregates one row per employer.
  In-pipeline checks (`engine/verify.py`) stop any run that looks wrong.
- **Layer 2 — "hiring now?" signal.** Deferred to v2. The report has a manual
  column instead (see below).
- **Layer 3 — reviewed gap read.** A human runs `prompts/gap_read.md` in their
  own Claude/ChatGPT, reviews the output, and saves it for the report to pick
  up. No script in this repo calls an LLM.

## Quickstart

Requires Python 3.10+.

```
python -m venv .venv
```

Activate it — the only OS-specific step:

- macOS/Linux: `source .venv/bin/activate`
- Windows: `.venv\Scripts\activate`

Then everything below is the same on every platform:

```
pip install -r requirements.txt
```

**Get the data.** Download one or more quarters of **LCA** disclosure data
(not PERM) from the DOL performance-data page:

> https://www.dol.gov/agencies/eta/foreign-labor/performance
> → *Disclosure Data* → **LCA Programs (H-1B, H-1B1, E-3)** →
> e.g. `LCA_Disclosure_Data_FY2025_Q4.xlsx` (~80–140 MB)
>
> The files resolve to direct links of the form
> `https://www.dol.gov/sites/dolgov/files/ETA/oflc/pdfs/LCA_Disclosure_Data_FY<YYYY>_Q<N>.xlsx`

Drop the file(s) into `data/raw/` **keeping DOL's original filename** — the
quarter label is derived from it.

**Run everything:**

```
python scripts/run.py
```

This converts the xlsx to parquet (minutes, streamed; skipped when already
done), builds and verifies the shortlist, and renders the report. It produces:

| Artifact | What it is |
| --- | --- |
| `output/sponsors_levelI.csv` | Public shortlist: one row per employer with filing counts, quarters, SOC titles, worksite states/cities, annualized wage min/median/max. |
| `output/sponsors_levelI.provenance.json` | Where every number came from: quarters used, filter funnel, values seen. |
| `output/private/runway_report.html` | Private, self-contained one-pager: shortlist table + gap read + caveats. Gitignored — it may sit next to portfolio/job-search details. |

Options: `--quarters FY2025Q4,FY2026Q1` asserts those quarters are loaded
(fails with instructions if one isn't; extra quarters found on disk are always
used). `--force-convert` re-converts xlsx even when the parquet looks current.

Run one invocation at a time. `run.py` is a single-operator tool; two runs at
once write the same files in `data/processed/` and `output/` and can corrupt
each other. Everything it writes is regenerable, so if a run is interrupted
just run it again (add `--force-convert` if a parquet was left half-written).

## The two manual inputs

**Hiring now? column.** The first report run creates a blank
`output/private/hiring_now.csv`. Fill its `hiring_now` (and optionally
`notes`) column by hand from real postings, then re-run
`python scripts/run.py`. The tool never fills it — an LCA certification says
nothing about current openings. Delete the file to get a fresh template after
the shortlist changes.

**Gap read.** Run `prompts/gap_read.md` in your own Claude/ChatGPT with the
applicant's portfolio, relevant shortlist rows, and a few hand-gathered
postings. Review the output, save the approved version to
`output/private/gap_read_filled.md`, and re-run. Until then the report shows a
visible "pending review" placeholder — and the run still succeeds.

## When something goes wrong

Every anticipated failure stops with a plain-English message, not a stack
trace:

- **"No converted LCA data found"** — nothing in `data/raw/`; follow *Get the
  data* above.
- **"...missing required column(s) ... PERM disclosure instead of an LCA
  one?"** — you downloaded the wrong file type; get the **LCA Programs** file.
- **"Requested quarter(s) not converted yet"** — you asked for a quarter via
  `--quarters` that has no data; the message names it and how to add it.
- **A `[verify]` check failed** — the run produced numbers that don't
  self-check (or the FY2025Q4 golden anchor moved). Don't trust the artifacts;
  investigate first.

## Caveats — attached to every applicant-facing output

- An LCA certification is not a hire or an open role.
- OPT is not sponsorship — a new grad's first job is on OPT; sponsorship comes 1-3 years later.
- Design roles are likely not STEM-OPT eligible -> roughly a 12-month OPT window, not 36.
- Employer names are conservatively normalized and may under-merge.
- Career/portfolio guidance, not immigration legal advice.

## Repo map

```
engine/sponsors.py           deterministic engine: filter + aggregate (no LLM, no HTML)
engine/verify.py             in-pipeline checks; a failed check stops the run
scripts/convert_quarters.py  raw DOL xlsx -> narrow parquet (streamed)
scripts/build_shortlist.py   engine -> output/sponsors_levelI.csv (+ provenance)
scripts/build_report.py      csv -> output/private/runway_report.html
scripts/run.py               THE command: convert -> shortlist -> report
prompts/gap_read.md          reviewer prompt template (run by a human, elsewhere)
docs/decision_log.md         every fork in the road, and why
docs/build_status.md         where Runway sits in the Ship Pipeline + what finishes v0
data/raw/                    you drop DOL xlsx here            (gitignored)
data/processed/              derived parquet, regenerable      (gitignored)
output/private/              report + manual inputs            (gitignored)
```
