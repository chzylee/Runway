# Stay Here — sponsorship diagnostic for new-grad designers (v0)

For **international new-grad designers who need US visa sponsorship**: a grounded shortlist of
companies that **actually sponsor entry-wage designers**, plus a review that names the **3 projects**
that would make a portfolio worth a visa to those companies. Validated so far with one real designer,
but built for the whole group — not one person.

Not a directory of "who sponsors anyone" (h1bgrader, MyVisaJobs, h1bdata already do that). The edge
is **data-grounding + advice**, in three parts:

1. **Find** — which employers actually sponsor design roles at the entry wage (`PW_WAGE_LEVEL = I`),
   read straight off mandated DOL filings.
2. **Assess** — read the applicant's portfolio (a resume works too, with less signal).
3. **Bridge** — the judgment step: given those companies' real postings + the portfolio, name the gap
   and the 3 concrete things to build to close it. **This bridge is the core of the tool.**

> **v0 scope:** by hand, no app. The grounded shortlist + a human-reviewed portfolio review. The
> OPT-now postings pipeline is deliberately deferred to a later version — see `docs/decision_log.md`.

## What's here

```
engine/
  sponsors.py      # the engine (NO LLM): find + rank entry-wage design sponsors from DOL data
  verify.py        # verification gate: column/non-empty/collapse/golden checks (stops a bad run)
scripts/
  convert_quarters.py  # raw DOL xlsx -> narrow parquet (run once per quarter)
  build_shortlist.py   # thin caller: provenance + verify + write the shortlist CSV
  build_report.py      # self-contained HTML one-pager
prompts/
  gap_read.md      # the portfolio review — the human-reviewed judgment step (run in your own Claude/ChatGPT)
docs/
  decision_log.md  # the forks and why (the design/judgment trail)
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

2. **Convert + build the shortlist** (runs the verification cell — a failed check stops the run):
   ```bash
   .venv/bin/python scripts/convert_quarters.py
   .venv/bin/python scripts/build_shortlist.py        # -> output/sponsors_levelI.csv
   ```

3. **Build the report:**
   ```bash
   .venv/bin/python scripts/build_report.py           # -> output/private/stay_here_report.html
   ```

4. **Portfolio review (the judgment step):** fill the four blocks in `prompts/gap_read.md`, run it in
   your own Claude/ChatGPT, review the output, save it to `output/private/gap_read_filled.md`, and
   rerun step 3 to slot it in.

## Adding another role later (v2 door, kept open)

One line in `engine/sponsors.py`:
```python
ROLE_SOC["consultant"] = ["13-1111"]   # + add titles to SOC_TITLES
```
Then `build_shortlist.py --role consultant`. (Per-role OPT/visa *judgment* is real work and stays
v2 — the engine just stops blocking it.)

## Caveats (also stated in the report)

- **An LCA is not a hire-now signal** — it's "this employer sponsors at entry wage," not "they'll
  hire you this month." New grads typically start on OPT/STEM-OPT.
- **Design is likely not STEM-OPT eligible** → a shorter (~12-month) OPT runway.
- Career/portfolio guidance, **not immigration legal advice**.
