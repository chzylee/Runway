# Stay Here — new-grad sponsorship diagnostic (v0)

For an international new-grad **designer** who needs US visa sponsorship: a
grounded shortlist of companies that **actually sponsor entry-wage designers**,
plus a portfolio gap-read that names what 3 projects would make her worth a visa
to those companies.

Not a directory of "who sponsors anyone" (h1bgrader, MyVisaJobs, h1bdata already
do that). The differentiator is **data-grounding + advice**: the shortlist is
read straight off mandated DOL filings at the entry wage tier (`PW_WAGE_LEVEL = I`).

> **v0 scope:** n=1, by hand, no app. One grounded signal (Layer B) + a reviewed
> gap-read (Layer 3). The OPT-now postings pipeline (Layer A) is deliberately
> **cut to v2** — see `docs/decision_log.md`.

## What's here

```
engine/
  sponsors.py      # Layer 1 engine (NO LLM): ROLE_SOC + build_sponsor_table()
  verify.py        # T2 verification: column/non-empty/collapse/golden checks
scripts/
  convert_quarters.py  # raw DOL xlsx -> narrow parquet (run once)
  build_shortlist.py   # thin caller: provenance + verify + write CSV
  build_report.py      # self-contained HTML one-pager
prompts/
  gap_read.md      # the reviewed LLM gap-read prompt (run in your own Claude/ChatGPT)
docs/
  decision_log.md  # FDE proof: the forks and why
data/raw/          # downloaded DOL files (gitignored, large)
data/processed/    # derived parquet (gitignored, regenerable)
output/            # sponsors_levelI.csv (public) + private/ report (gitignored)
```

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run

1. **Download a DOL LCA quarter** into `data/raw/` (FY2025, 2021+). Files:
   `https://www.dol.gov/sites/dolgov/files/ETA/oflc/pdfs/LCA_Disclosure_Data_FY2025_Q4.xlsx`
   (Q1–Q4 available; the full year gives the strongest repeat-sponsor signal).

2. **Convert + build the shortlist** (runs the verification cell — a failed check
   stops the run):
   ```bash
   .venv/bin/python scripts/convert_quarters.py
   .venv/bin/python scripts/build_shortlist.py        # -> output/sponsors_levelI.csv
   ```

3. **Build the report:**
   ```bash
   .venv/bin/python scripts/build_report.py           # -> output/private/stay_here_report.html
   ```

4. **Gap-read (the LLM step):** fill the four blocks in `prompts/gap_read.md`,
   run it in your own Claude/ChatGPT, review the output, save it to
   `output/private/gap_read_filled.md`, and rerun step 3 to slot it in.

## Adding another role later (v2 door, kept open)

One line in `engine/sponsors.py`:
```python
ROLE_SOC["consultant"] = ["13-1111"]   # + add titles to SOC_TITLES
```
Then `build_shortlist.py --role consultant`. (Per-role OPT/visa *judgment* is
real work and stays v2 — the engine just stops blocking it.)

## Caveats (also stated in the report)

- **An LCA is not a hire-now signal** — it's "this employer sponsors at entry
  wage," not "they'll hire you this month." New grads start on OPT/STEM-OPT.
- **Design is likely not STEM-OPT eligible** → ~12-month OPT runway.
- Career/portfolio guidance, **not immigration legal advice**.
