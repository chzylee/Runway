# Runway — sponsorship diagnostic for new-grad designers (v0)

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
  run.py               # THE command: convert + shortlist + report, end to end
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
# macOS/Linux
python3 -m venv .venv && source .venv/bin/activate

# Windows (git bash)
python -m venv .venv && source .venv/Scripts/activate

# then identical on both, venv active:
pip install -r requirements.txt
```

## Run

Activate the venv (see above) once per shell session. Then it's **two steps**: get the data, run one command.

1. **Download a DOL LCA quarter** into `data/raw/`.
   - Browse and download from the DOL page:
     **https://www.dol.gov/agencies/eta/foreign-labor/performance**
     → under *Disclosure Data*, **LCA Programs (H-1B, H-1B1, E-3)**.
   - As of writing, the newest published quarter is **FY2026 Q2**. Any FY2021+ quarter works; a full
     year of quarters gives the strongest repeat-sponsor signal (with a single quarter, no employer
     can show as a repeat sponsor).
   - Keep DOL's original filename (e.g. `LCA_Disclosure_Data_FY2026_Q2.xlsx`). Drop as many quarters
     as you like into `data/raw/` — the tool uses whatever is there.

2. **Run the whole pipeline** — convert, build the shortlist, build the report, in one command:
   ```bash
   python scripts/run.py
   ```
   It figures out which quarters still need converting, runs the verification gate (a failed check
   stops the run), and writes:
   - `output/sponsors_levelI.csv` — the public grounded shortlist
   - `output/private/runway_report.html` — the shareable one-pager (open in a browser)

   If there's no data yet, it tells you exactly where to get it instead of erroring out.

3. **Hiring-now check (manual):** the first report build creates `output/private/hiring_now.csv`
   with every shortlist employer and a blank `hiring_now` column. For the companies you actually
   care about, eyeball their careers page and fill in **yes / no / unclear**, then run
   `python scripts/run.py` again — the report's "Hiring now?" column shows your answers. (LCA data
   can't answer "hiring now"; this manual check is the v0 stand-in for the postings pipeline that's
   deliberately deferred — see `docs/decision_log.md`.)

4. **Portfolio review (the judgment step):** fill the four blocks in `prompts/gap_read.md`, run it in
   your own Claude/ChatGPT, review the output, save it to `output/private/gap_read_filled.md`, and
   run `python scripts/run.py` again to slot it into the report.

> The three underlying scripts (`convert_quarters.py`, `build_shortlist.py`, `build_report.py`) still
> run individually if you want them — `run.py` just chains them. `build_shortlist.py --quarters
> FY2025Q4` pins a specific set; with no flag it uses every quarter you've converted.

## Adding another role later (v2 door, kept open)

One line in `engine/sponsors.py`:
```python
ROLE_SOC["consultant"] = ["13-1111"]   # + add titles to SOC_TITLES
```
Then `build_shortlist.py --role consultant`. (Per-role OPT/visa *judgment* is real work and stays
v2 — the engine just stops blocking it.)

## Caveats (also stated in the report)

- **An LCA certification is not a hire or an open role** — it's "this employer sponsors at entry
  wage," not "they'll hire you this month."
- **OPT is not sponsorship** — a new grad's first job is on OPT; sponsorship typically comes 1–3
  years later.
- **Design is likely not STEM-OPT eligible** → a shorter (~12-month) OPT runway.
- **Employer names are conservatively normalized and may under-merge** — the same parent company
  can appear under more than one legal spelling.
- Career/portfolio guidance, **not immigration legal advice**.
