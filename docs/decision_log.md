# Decision log

Every fork in the road that had a real alternative, and why we took the branch
we took. Newest entries at the bottom.

## 1. Data source: DOL LCA disclosure data, not PERM, not third-party sites

**Alternatives:** PERM disclosure data (green-card labor certs), USCIS H-1B
Employer Data Hub, scraped aggregators (MyVisaJobs etc.).

**Why LCA:** An LCA filing is the moment an employer commits money to a work
visa for a specific role at a specific wage level — the closest public signal
to "this company sponsors people like you." PERM measures green cards years
into employment, which lags a new grad's question by half a decade. USCIS data
lacks SOC/wage-level detail per filing. Third-party sites repackage the same
DOL files with unknown transformations; going to the source keeps every number
auditable. The files are public record, so the shortlist CSV can be public.

## 2. Filter: CASE_STATUS = Certified, PW_WAGE_LEVEL = I

**Alternatives:** all statuses; all wage levels; a wage-dollar cutoff instead
of the level.

**Why:** Certified-only counts filings the government actually accepted —
denied/withdrawn filings prove intent, not capacity. Level I is DOL's own
definition of "entry level" for the occupation and area, which is exactly a
new grad's tier; a dollar cutoff would need per-metro calibration that Level I
already encodes. "Certified - Withdrawn" is deliberately excluded (exact match
on "Certified") because a withdrawn filing didn't result in an employed visa
holder. The cost: Level I is a proxy — some new-grad hires are filed at Level
II — so the shortlist under-counts rather than over-promises.

## 3. Design SOC codes seeded as a role dict

**Alternatives:** hardcode the three codes in the filter; try to catch design
jobs by JOB_TITLE keywords.

**Why:** `ROLE_SOC = {"design": ["15-1255", "27-1024", "27-1021"]}` makes
adding a role later a one-line change and keeps v0 scoped to design only.
The three codes (web/digital interface designers, graphic designers,
commercial/industrial designers) are treated equally — "primary" is
descriptive only. Title-keyword matching was rejected: employer-written titles
are noisy, SOC codes are what the wage level is certified against.

**Detail-suffix scope (amended 2026-07-04):** DOL SOC codes carry an O*NET detail suffix
(`15-1255.00`, `15-1255.01`, ...). `normalize_soc` matches on the base code (`split(".")[0]`),
so **every detail occupation under a base code is included**, not just the generic `.00`. This
is deliberate — the wage level certifies against the base occupation — but it was an unstated
consequence of the implementation until the Test Spec pinned it (TEST_SPEC F6). Consequence to
own: `15-1255.01` = Video Game Designers, so those filings count as "design" — in FY2025Q4, 3 of
67 selected filings (employers incl. Activision) enter the shortlist this way, traceable via the
`soc_titles` column. Full SOC/O*NET vocabulary lives on the project wiki's Core Domain Knowledge
page.

## 4. The "hiring now?" signal is manual in v0

**Alternatives:** scrape job boards / careers pages and classify postings
automatically (the design doc's Layer 2 / Layer A).

**Why deferred to v2:** postings pipelines rot fast (markup changes,
anti-scraping, classifier drift) and would dominate maintenance for a v0 whose
edge is the LCA grounding. Instead the report has a "hiring now?" column the
reviewer fills by hand in `output/private/hiring_now.csv`; the tool creates
that file blank and never writes to it again (delete it to get a fresh
template). Cheap-to-add was not a reason to add.

## 5. Engine/report split

**Alternatives:** one script that filters and renders HTML in one pass.

**Why:** `engine/` returns data tables and knows nothing about HTML (or LLMs,
or printing); `scripts/` own I/O, console output, and rendering. This keeps the
part that must be trustworthy (numbers) testable in isolation from the part
that will churn (presentation), and it makes "the engine never calls an LLM" a
structural property instead of a promise.

## 6. Conversion keeps all rows, filtering happens at query time

**Alternatives:** filter to certified design Level-I rows during xlsx -> parquet
conversion for smaller files.

**Why:** the parquet is a narrow (12-column) but complete copy of the quarter,
so adding a role or changing a filter never requires re-streaming a 100 MB
xlsx. The size cost is small because the columns are few.

## 7. Conversion skips up-to-date parquet; `--force-convert` overrides

**Alternatives:** reconvert every run (simple, slow); never reconvert (stale
after a re-download).

**Why:** streaming a DOL xlsx takes minutes, and `run.py` is meant to be run
casually. A parquet is reused when it is newer than its xlsx (file mtime), so
re-downloading a corrected quarter triggers reconversion automatically and
`--force-convert` covers tool-version upgrades.

## 8. Wage annualization: FROM rate x {YEAR: 1, HOUR: 2080, MONTH: 12, WEEK: 52}

**Alternatives:** midpoint of FROM/TO; include DOL's "Bi-Weekly" unit; drop
filings with unparseable wages.

**Why:** the FROM rate is the guaranteed floor and is always present; TO is
often blank, so a midpoint would mix two different quantities across rows. The
four multipliers cover the spec'd units; a filing with any other unit (or an
unparseable wage) **stays in every count** but contributes no wage statistics —
dropping the filing would silently understate a sponsor's activity. The count
of wage-excluded filings is reported in provenance and in the report footer,
never silently.

## 9. Employer normalization strips exactly LLC / INC / CORP / LTD

**Alternatives:** aggressive canonicalization (strip LLP, PLLC, CO, GROUP,
HOLDINGS...; fuzzy matching).

**Why conservative:** merging two genuinely different employers is a worse
error for an applicant than listing one employer twice — the caveat on every
output says names "may under-merge," and that direction is deliberate.
Uppercasing, collapsing punctuation, and stripping the four unambiguous
suffixes catches the common "Acme LLC" / "ACME, Inc." split; everything beyond
that (e.g. "Deloitte Consulting LLP" keeps its LLP) waits until a real merge
failure justifies it.

## 10. Repeat sponsor = present in >= 2 distinct quarters

**Alternatives:** filing-count threshold; weighting recent quarters higher.

**Why:** the question a repeat flag answers is "does this employer keep coming
back," and distinct quarters measure exactly that, independent of how many
positions one batch filing covered. With a single quarter loaded the flag is
structurally "no" for everyone, so the report says the signal is unavailable
rather than implying nobody repeats. Two is the smallest number that means
"again" — any higher is arbitrary without more history.

**Amended (2026-07-04, dec. #21):** because DOL files are cumulative FYTD, same-FY
quarters are collapsed to the latest before aggregation, so "distinct quarters"
is now effectively "distinct **fiscal years**" — within-FY quarter repeat isn't
measurable from cumulative files (no `DECISION_DATE` kept). The signal is
unchanged in spirit ("keeps coming back"); the reliable unit is the fiscal year.

## 11. `--quarters` asserts expectations; the run always uses every quarter present

**Alternatives:** `--quarters` as a hard selector that excludes other data.

**Why:** the two failure modes the spec distinguishes are (a) an extra quarter
present that wasn't requested — harmless, more signal, just use it — and (b) a
requested quarter with no converted data — the user believes data is there and
it isn't, which must stop the run with instructions naming the quarter. Making
the flag an expectation check implements exactly that split; a selector would
add an exclusion feature nobody asked for.

**Amended (2026-07-04, dec. #21):** "an extra quarter present is harmless, just
more signal" holds only *across* fiscal years. Two quarters of the *same* fiscal
year are cumulative (FYTD), so the extra one is not more signal — it is overlap
that would double-count. Same-FY quarters are now superseded to the latest file;
extra *different-FY* quarters are still simply used, as this decision intends.

## 12. Golden check pinned to FY2025Q4 / iGavel

**Alternatives:** no golden check; recomputing against a stored full snapshot.

**Why:** the 2026-07-01 manual run of this pipeline on the real
`LCA_Disclosure_Data_FY2025_Q4.xlsx` established iGavel, Inc. (7 filings) as
that quarter's top Level-I design sponsor, and that was human-verified against
the raw file. `engine/verify.py` recomputes FY2025Q4 from its own rows on
every run that includes it and fails loudly if the top employer changes —
catching filter or normalization drift. When FY2025Q4 isn't loaded the check
**skips** (it can't fire a false failure on other data). A full snapshot diff
was rejected as a maintenance burden disproportionate to v0.

## 13. The report shows the full table — no top-N cutoff

**Alternatives:** show top 20/50 and point to the CSV for the rest.

**Why:** Level-I design filings are inherently sparse (FY2025Q4: ~50
employers), so a cutoff solves a problem the data doesn't have — and any N
would be a magic number. If a future multi-year run makes the table unwieldy,
that's the moment to add (and log) a threshold. The CSV remains the canonical
artifact either way.

## 14. UTF-8 is forced everywhere

**Alternatives:** trust the platform defaults.

**Why:** the target environments include a Japanese-locale Windows console
(cp932), which crashes on employer names and typographic characters the moment
anything prints or writes with locale defaults. Every entry point reconfigures
stdout/stderr to UTF-8 and every file open passes `encoding="utf-8"`, so the
locale never decides whether a run succeeds. (Learned the hard way in a
previous build.)

## 15. Errors are RunwayError with a plain-English message

**Alternatives:** let exceptions propagate; error codes.

**Why:** the person running this is not the person who wrote it. Every
anticipated failure — no data, PERM file, missing requested quarter, failed
verification — raises `RunwayError` whose message says what happened and what
to do next; the CLI wrapper prints it and exits 1. Stack traces are reserved
for genuine bugs.

## 16. Fully empty xlsx rows are dropped at conversion

**Alternatives:** keep them (the certified filter removes them anyway).

**Why:** the real FY2025Q4 file declares 563,689 rows but only 118,580 hold
data — the rest are empty padding from the sheet's declared dimensions.
Keeping them wouldn't change the shortlist, but every "derived from N rows"
statement in provenance and the report would be off by ~4x. Rows where all 12
kept columns are empty are skipped during streaming and the skip count is
printed, so nothing disappears silently.

## 17. Gap-read markdown gets a ~40-line renderer instead of a dependency

**Alternatives:** add `markdown`/`mistune` to requirements; require the
reviewer to save HTML; embed the markdown in `<pre>`.

**Why:** the reviewed gap read needs headings, lists, bold, and links — a
bounded subset a small function renders safely (input is HTML-escaped first).
Adding a dependency for that widens the install surface of a tool whose
requirements are deliberately three lines; `<pre>` would make the flagship
section of the report look broken.

## 18. Clean clones ship `data/raw/` via `.gitkeep`, not runtime `mkdir`

**Alternatives:** create `data/raw/` at runtime in `run.py`; add a "create
the folder" step to the README.

**Why:** README step 1 tells the user to drop the DOL xlsx into `data/raw/`
before any command runs, so the folder must exist the moment the clone does —
runtime creation is too late for that step, and a manual-mkdir README step
adds friction to the primary path. `.gitkeep` + a gitignore negation
(`data/raw/*` / `!data/raw/.gitkeep`) keeps the drop point in the repo while
still ignoring the large data files. (Adopted from the comparative build
review's graft list, 2026-07-02; entry added after the delta re-review
flagged the fork as unlogged.)

## 19. v0 Acceptance Gate passes on the human legs; the automated suite is the Test Build step

**Alternatives:** hold the gate open until the automated suite (TEST_SPEC must-index) is built
and green — one combined "gate PASS" that folds test-writing into the gate.

**Why (option b):** TEST_SPEC §5 already scopes test-*writing* as a separate build step, so
requiring a green suite *inside* the acceptance gate contradicts the spec's own boundary. The v0
gate is recorded as passed on the two legs a person actually verified — Scenarios A/B green and
the human pass (spot-trace of iGavel=7 and Deloitte=2 + real-user read), done from demonstrated
ownership after the Acceptance-Gate recovery — with the automated suite carried forward as the
Test Build deliverable that completes §7's third leg (its own acceptance = the §8 trust-check:
V1–V4 must fire, ⚠ tests must fail first, fresh-context assertion review). Recording only the
verified legs is the anti-"OK-clicking" discipline applied to the gate itself: no green light is
claimed that isn't real. Ratified by the owner 2026-07-04.

*(Surfaced two system-level standards, elevated to the Ship Pipeline / Reviews and Changes rather
than kept here: (1) a real user in testing is required for any main-lane project — skippable only
for sidequest-tier, black-box builds; (2) every Claude-Code-generated pipeline step ships a
recorded prompt — here, a Test Build Prompt — for retracing and accountability.)*

## 20. v0 build-complete requires the 9 deferred MUST behaviors built, not shipped-deferred

**Alternatives:** ship v0 with the nine `xfail` behaviors logged as a v0.1 backlog and
go straight to own-your-code — the automated suite is already green, so TEST_SPEC §2's
"suite green" leg is technically met.

**Why (build them first):** the nine deferred tests include MUST-tier failure modes, not
cosmetics. Cumulative-quarter double-counting (F1/I8) fabricates the repeat-sponsor
signal the product sells; a cp932-saved manual input (F2) crashes with a raw traceback
on the exact JP-locale machine dec. #14 exists for; an unreadable parquet (F3)
sticky-poisons runs; the M13 href breakout is a live injection. own-your-code (the next
stage) confers the ability to *defend* the code — shipping v0 with known MUST failure
modes unbuilt would write un-ownable behavior into the onboarding doc. TEST_SPEC marks
all nine ⚠ "the build must catch up to," so deferral was always framed as temporary.
This resolves the surface tension between §2 ("a green suite ... trusted to ship") and
those ⚠ markers: the green suite is necessary, not sufficient; the ⚠ behaviors are owed
before own-your-code. Position and per-item scope are tracked in `docs/build_status.md`.
Ratified by the owner 2026-07-04.

## 21. Cumulative same-FY quarters: supersede to the latest file, not dedupe or refuse

**Context:** DOL quarterly disclosure files are cumulative fiscal-year-to-date —
`FY2099Q2` contains all of `FY2099Q1`'s filings plus Q2's new ones. Loading both
same-FY files counted every shared filing twice and fabricated the
`repeat_sponsor` signal (a filing listed in two same-FY files looked like an
employer "coming back"). This is the F1/I8 failure mode and MUST-tier (dec. #20):
the repeat signal is the product's edge. dec. #11's "an extra quarter is harmless,
just more signal" was true across fiscal years, false within one.

**Alternatives:**
- **(A) Refuse** — stop the run when two same-FY quarters are loaded.
- **(C) Dedupe** — drop filings that are identical across same-FY quarter files,
  keep the genuinely-new ones (occurrence-rank to preserve within-quarter
  multiplicity, since no `CASE_NUMBER` is kept to key on).
- **(B) Supersede** — within a fiscal year, keep only the latest quarter file
  (the cumulative superset); different fiscal years are always kept.

**Why supersede (B):** a deeper domain fact settled it — cumulative FYTD files make
*within-fiscal-year* quarter repeat **fundamentally unmeasurable**: a cumulative
`Q2` file says a filing happened "sometime in FY2099 to date," and without
`DECISION_DATE` (not kept) you cannot place it in Q1 vs Q2. So the honest unit of
"keeps coming back" is the **fiscal year**, and superseding to the latest same-FY
file models the data as it actually is — no filing-identity guess, no multiplicity
edge cases. Refuse (A) was rejected as user-hostile and contrary to dec. #11's
"use every quarter present"; dedupe (C) was rejected because it preserves a
same-FY quarter-repeat signal that the cumulative structure makes noise, and needs
a full-row identity proxy (no `CASE_NUMBER`) with occurrence-rank machinery to
avoid under-counting legitimately-identical filings.

**Cost paid, in the open:** supersede changed the meaning of `repeat_sponsor` from
"≥2 distinct quarters" (dec. #10) to "≥2 distinct fiscal years," which broke two
existing MUST tests that built their repeat case from same-FY quarters — **M6**
(`test_M6_per_employer_row_is_correct`) and **M14**
(`test_M14_no_single_quarter_note_with_two_quarters`). Both fixtures encoded the
very same-FY-additive misconception being corrected, so both were amended to use
different fiscal years (FY2099Q1 + FY2100Q1) and logged here — a deliberate,
ratified fixture correction, not a quiet edit-to-pass. Transparency: superseded
quarters are announced on the console and recorded in provenance
(`quarters_superseded`), so nothing disappears silently (dec. #16).

Implemented as `engine.sponsors.supersede_cumulative_quarters`, called at the top
of `build_sponsor_table`. Strikes the F1 design amendment owed in TEST_SPEC §5.1.
Ratified by the owner 2026-07-04 (re-confirmed after the M6 blast-radius finding).

## 22. v1 data refresh runs as a scheduled GitHub Action, discovering quarters by HEAD-probing DOL

*Ratified 2026-07-06 (v1 Automated-Pipeline stage). Both sub-choices below
resolved the same session.*

v0 sourced data by hand: a human downloaded the xlsx from DOL and dropped it in
`data/raw/`, and `convert_quarters.py` discovered it by globbing that folder
(the DOL filename being the schema). v1 needs the data preprocessed in CI and the
parquet served to a GitHub Pages frontend, so the drop has to be automated.

**Alternatives for the trigger:** (A) run on every push; (B) a scheduled cron;
(C) a manual-only `workflow_dispatch`.

**Why scheduled + dispatch (B+C):** the source data moves *quarterly*, so matching
the trigger to dev cadence (A) is pure waste, and worse — the job commits parquet
back to the repo, so a push trigger risks a self-triggering commit loop. DOL can't
notify us, so a `schedule:` is the honest shape; **weekly** (`17 6 * * 1`, off the
hour to dodge GitHub's congested `:00` slots) because the upstream-vs-committed
diff makes ~51 of 52 runs free no-ops, weekly absorbs GitHub's cron delays/skips,
and a roughly-weekly run keeps the repo active enough to sidestep the 60-day
auto-disable that a sparse monthly/quarterly schedule would risk. `workflow_dispatch`
adds a manual button for the day a quarter drops — the affordance that replaces
"drop a file in data/raw/."

**Discovery mechanism:** CI has no human to drop files, so `fetch_quarters.py`
discovers what's *published upstream* by HEAD-probing DOL's stable direct-link
template (README) across a fiscal-year window — a 200 means published, a 404 means
not yet. Incrementality is keyed on **quarter identity** (is this quarter's parquet
already committed?), NOT on the mtime skip `convert_quarters.py` uses locally:
git doesn't preserve mtimes and the raw xlsx is never committed, so mtime is
meaningless in CI. The convert+shortlist+commit steps run only when fetch reports
`changed=true`, so "only process when there's new data" is real, not just cheap.

**Resolved sub-choices:**
- **Lookback window = `LOOKBACK_FISCAL_YEARS = 1`** (current FY + prior). Rolling
  window chosen over a committed manifest of known quarters: self-healing and
  simpler, at the cost of a handful of extra HEAD probes vs an auditable list.
  *Why 1:* it is the recency the domain wants (recent certified Level-I filings are
  the "actively sponsors entry-level design" signal; older filings age out — DOL's
  own "Active %" framing) **and** the floor that preserves the product's edge — the
  `repeat_sponsor` signal needs ≥2 distinct fiscal years (dec. #10/#21), and 1
  keeps exactly current FY + prior FY = 2 FYs. It also matches the applicant's real
  question: sponsorship lands 1-3 years into a job, so the best predictor is "is
  this employer sponsoring consistently *right now*," which two recent FYs capture.
  *Risk + review:* certified Level-I **design** filings are a thin slice, so a
  narrow window could yield a sparse shortlist. Mitigation: `LOOKBACK_FISCAL_YEARS`
  is a one-line constant — after the first real FY2026Q1 pull, eyeball the employer
  count and widen to 2 only if too thin. Ship 1, measure, adjust.
- **Storage granularity = highest available quarter per fiscal year.** DOL files
  are cumulative FYTD (dec. #21), so within a fiscal year only the latest quarter is
  kept; a superseded same-FY parquet is pruned when a newer one lands, and parquet
  outside the lookback window is pruned too. **The lookback window is the set of
  files maintained** — `data/processed/` is reconciled to exactly {latest quarter
  per FY in window}. Over time this holds ~1-2 years of data (current FY partial +
  prior FY full). The engine already dedupes at aggregation; this is the
  storage-side of the same rule, keeping the committed repo lean.

  **Amended (2026-07-06, dec. #27):** "reconciled to exactly {latest per FY in window}"
  was implemented as "prune any committed parquet not in this run's upstream set,"
  which lets a single transient HEAD-probe failure delete valid committed data. The
  prune rule is narrowed to its two safe reasons only — supersession and out-of-window;
  never a probe-miss. See dec. #27.

## 23. Processed parquet is committed to the repo (supersedes v0's "regenerable, don't commit")

*Ratified 2026-07-06 (v1).*

v0 gitignored all of `data/processed/` — the parquet was a local, regenerable
build artifact (the mtime skip in dec. #7 existed precisely because it was cheap to
keep around but never shipped). v1's GitHub Pages frontend consumes the parquet, so
it must live in the repo.

**Alternatives:** (A) commit the parquet; (B) keep it gitignored and have the Pages
build regenerate it from the raw xlsx on every deploy; (C) store it as a build
artifact / release asset outside the repo.

**Why commit (A):** the parquet is narrow (columns-subset) and tiny — ~2.8 MB per
quarter — so the usual "don't commit large binaries" objection doesn't apply.
Regenerating on every Pages deploy (B) means re-downloading 80-140 MB and streaming
a multi-minute conversion for data that changes 4x/year — wasteful and slow.
Committing makes the frontend's input versioned, diffable, and served straight from
the repo with no build-time data step. `.gitignore` now un-ignores
`data/processed/*.parquet` while keeping any other derived file there ignored.

## 24. v1 pipeline stores one shortlist parquet per title, incrementally, keyed on (title x window)

*Ratified 2026-07-06 (v1 Automated-Pipeline stage). One sub-fork left open — see
"zero-result title" below — because it cannot be decided until a second title exists.*

v1 serves a per-title shortlist to the GitHub Pages frontend, and the processing
must be incremental: re-running should touch only what isn't already saved. The
engine was already title-agnostic (`build_sponsor_table` takes SOC codes, not a
role name), so this is a new *build loop + storage + bookkeeping* layer, not an
engine change.

**The unit of work is a (title, window) pair.** A title's stored parquet is
"already saved" iff it exists AND its manifest records the *current* quarter window
(the set in data/processed/ after cumulative-FYTD supersession, dec. #21). This
yields exactly the two promised triggers: a new quarter shifts the window so every
title rebuilds; a newly-added title has no stored parquet so only it builds;
nothing-changed is a no-op. Verified locally: build then skip-when-current both
behave (76 employers / 95 filings for `design` over FY2025Q4+FY2026Q1).

**Storage + manifest:** `output/shortlists/<title>_levelI.parquet` is the frontend's
data; `output/shortlists/index.json` is the manifest — per title it records the
window built from, SOC codes, and counts. The manifest is both the saved-state this
script diffs against AND the list the frontend reads to know which titles exist, so
the title registry does not need to be duplicated for the frontend.

**Decisions inside this one:**
- **Titles stay in `engine.ROLE_SOC` (dec. #3 stands).** Adding a title is one
  entry there; the frontend reads the *emitted* `index.json`, not the registry, so
  there's no second source of truth to keep in sync. Rejected: externalizing to a
  `config/titles.json` — it would enable a scoped `push`-trigger, but adds a config
  file and a sync concern for no benefit the manifest doesn't already give.
- **`build_shortlists.py` always runs in CI; `convert` stays gated on new quarters.**
  Convert is the only expensive step (streaming 80-140 MB), so it stays behind
  fetch's `changed`. The shortlist build is cheap (few-MB parquet) and must run
  every time — that is the only way a title added *without* a new quarter gets
  built. Commit fires if fetch OR build reports a change.
- **Additive to v0.** The v0 single-title private-report path (`build_shortlist.py`
  -> `output/sponsors_levelI.csv`, `build_report.py`) is left untouched; the
  multi-title site pipeline is a parallel new path. The frontend will likely absorb
  the private report later — a deliberately deferred v1 decision, not a mid-stream
  teardown of a tested path.

**Open sub-fork — zero-result title:** `engine.verify.check_nonempty` *raises* on a
title that selects zero entry-wage filings, which today would hard-stop the whole
pipeline. Harmless now (only `design` exists, 76 employers). But when a second title
is added, we must decide: (A) keep hard-fail — a title you added should have data,
and its absence is worth stopping for; or (B) per-title isolation — record an empty
shortlist for that title, log it, and keep building the others. Deferred until title
#2 forces the choice; flagged here so it isn't discovered in production.

**RESOLVED (2026-07-06, dec. #25):** neither pure option — **split by failure kind.**
An *empty-result* title is isolated (marked `empty` in the manifest, others still
build); an *integrity-check* failure still aborts the whole run. See dec. #25.

**Amended (2026-07-06, dec. #26):** the "already saved" test — written here as keyed on
the (title × window) pair — is tightened to (title × **definition** × window) so a SOC
edit without a new quarter still rebuilds. **Amended (2026-07-06, dec. #29):** the
`--titles` flag scopes the *build* only and never prunes out-of-subset titles.

## 25. Per-title build failure: isolate an empty title, abort on an integrity failure

*Ratified 2026-07-06 in the v1 data-pipeline Test Spec (RATIFICATION_LOG_v1.md,
Sitting 2, call A). Closes the open sub-fork in dec. #24. Currently red — the code
hard-stops on both kinds; the build owes the isolation half.*

The multi-title loop (`build_shortlists.py`) calls `build_sponsor_table` then
`verify.run_all` per title, and both *raise* `RunwayError` on trouble — so today the
first bad title aborts the whole run and no title's shortlist is written. dec. #24
left open how to handle a title that can't be built once a second title exists.

**Resolved: split by failure kind, not one blanket policy.**
- **Empty result** (a title's SOC codes match zero certified Level-I filings) is a
  *normal outcome* for a thin niche role → isolate it: mark it `empty` in its manifest
  entry, keep building every other title. One sparse title must never block the site.
- **Integrity-check failure** (`check_filing_count_sum`, `check_employer_collapse`)
  still aborts the whole run. These don't mean "this title's data is odd" — they mean
  the engine is miscounting, which corrupts *every* title in the run. Isolating and
  recording it as "one title skipped" would ship the corrupted siblings while the check
  that says *do not trust this run* is filed away.

**Rejected: (A) pure hard-fail** — one empty niche title takes down the whole site,
which does not scale past title #2. **(B) pure isolation** — swallows a systemic engine
bug as a per-title skip, breaking the v0 verify trust contract (TEST_SPEC §1/§8: a check
that can't stop a bad run manufactures confidence). The split keeps robustness for the
expected case and loudness for the dangerous one.

## 26. Incremental "already saved" is keyed on (title × definition × window), not just window

*Ratified 2026-07-06 (Test Spec, call C). Tightens dec. #24. Currently red — the code
compares only the window.*

dec. #24 defined a title as "already saved" iff its stored parquet exists and its
manifest records the current quarter window. The implementation compares only the
window, and ignores the `soc_codes` it already stores in the manifest. Consequence:
editing a title's SOC list in `ROLE_SOC` (dec. #3 — the intended way to refine a role)
*without* a new quarter leaves the window unchanged, so the title reads as up-to-date
and is **not** rebuilt — the frontend serves a shortlist that no longer matches the
title's definition, until the next quarter forces a rebuild or someone runs `--force`.

**Resolved:** the saved-state key includes the title's definition (`soc_codes`, and the
constant `wage_level`) alongside the window. Editing a title's codes marks it not-saved
and rebuilds it on the next run. The manifest already carries `soc_codes`, so this is a
comparison fix, not new state. This is the silent-wrong class the pipeline exists to
avoid: you edit the config, the run says "all titles current," and your change vanished.

## 27. Conservative prune: delete committed parquet only on supersession or out-of-window, never on a probe-miss

*Ratified 2026-07-06 (Test Spec, call B). Narrows dec. #22's prune step. Currently red —
the code prunes any committed quarter absent from this run's upstream set.*

dec. #22 said `data/processed/` is "reconciled to exactly {latest quarter per FY in
window}." That was implemented as: prune any committed parquet whose label isn't in the
set of quarters this run found published upstream (`want_labels`). Because discovery is
a set of live HEAD probes to a `.gov` CDN, and `quarter_is_published` collapses *any*
non-2xx (404, **503, 429**, timeout) to "not published," a single transient probe
failure on one fiscal year — while another FY still resolves, so the total-blackout
guard never fires — deletes that FY's valid committed parquet and commits the deletion.
The repeat-sponsor signal needs ≥2 distinct fiscal years (dec. #10/#21), so dropping one
FY silently collapses the product's core edge until a later run's probe succeeds.

**Resolved:** pruning is restricted to its two provably-safe reasons —
1. **supersession** — a *newer* same-FY quarter was *positively observed* (a 200), so the
   older same-FY file is redundant (cumulative FYTD, dec. #21); and
2. **out-of-window** — the FY is older than the lookback floor, which is pure calendar
   math independent of any probe.

An in-window FY that has committed parquet but no upstream 200 this run is **never**
pruned. This loses nothing real: DOL serves stable permanent links and does not
un-publish a quarter, so "present locally, absent upstream this run" can only be a
transient failure or a URL-template change — both of which must be *survived*, not acted
on. This is also all dec. #22 ever intended; the broad prune was an implementation
over-reach.

## 28. CI gating decisions live in a testable Python orchestrator, not YAML `if:` expressions

*Ratified 2026-07-06 (Test Spec, call E). New. Currently red — the gating lives in the
workflow YAML.*

The `data-pipeline.yml` workflow encodes real branching in GitHub Actions `if:`
expressions: convert runs only if fetch reported `changed`; commit runs if fetch OR
build reported `changed`; a failed `git push` has no defined recovery. None of that is
unit-testable — you cannot assert on YAML wiring from pytest, and the gating is exactly
the logic whose correctness protects committed data.

**Resolved:** the convert/commit/push **decisions** move into a `scripts/run_pipeline.py`
orchestrator that pytest can drive with fabricated `changed` flags, and the workflow
shrinks to `checkout → python scripts/run_pipeline.py → git push` (with the push retry
of dec. #30-adjacent K). The irreducible YAML residue — the `concurrency` group, the
`schedule`/`workflow_dispatch` triggers, `permissions`, and the raw `git push` plumbing —
stays in YAML and is verified by **code review only** (ratified: a full extraction of git
mechanics into Python buys little and adds indirection). The owner chose extraction over
the alternative of a one-time manual `workflow_dispatch` observation, judging deterministic
unit tests the stronger proof.

## 29. `--titles` scopes the build only; it never prunes out-of-subset titles

*Ratified 2026-07-06 (Test Spec, call G). New. Currently red — a scoped run deletes
every out-of-subset title.*

`build_shortlists.py --titles <subset>` was intended as a convenience to rebuild a named
subset. But the stale-title prune loop computes `set(prior_manifest) − set(built_this_run)`
and deletes any title's parquet not in that difference, and the manifest is rewritten with
only the titles built this run. So `--titles design` on a repo that also has `engineering`
**silently deletes** `engineering_levelI.parquet` and drops its manifest entry — a flag
meant to *scope* a run instead *removes* data.

**Resolved:** `--titles` restricts only which titles are *built*. Pruning of removed titles
always reconciles against the full `ROLE_SOC` registry, and the manifest always retains
entries for titles that exist but weren't in this run's subset. A scoped run can add or
refresh titles; it can never delete one. A title is removed only by removing it from
`ROLE_SOC` (dec. #24) — an explicit registry edit, not a side effect of a `--titles` flag.

## 30. Shortlist parquet is written atomically and its readability is verified before reuse

*Ratified 2026-07-06 (Test Spec, call H). New. Currently red — writes are direct and
"already saved" checks only file existence.*

`build_shortlists.py` writes each title's parquet with a direct `to_parquet(path)` (no
temp-then-rename), and the "already saved" check tests only that the file *exists*, never
that it *reads*. A process killed mid-write (a CI runner OOM/timeout during pandas/pyarrow
work is a real event) leaves a truncated `<title>_levelI.parquet`; because the prior
manifest entry still matches the window, the next run skips the rebuild and serves the
corrupt file to the frontend **forever, with no self-heal.** This is the exact failure
class dec. #20/F3 already fixed once on the *read* side (`load_quarters` wraps the read and
gives a `--force-convert` recovery path) — reintroduced here on the *write* side.

**Resolved:** mirror the anti-corruption pattern `fetch_quarters._download` already uses —
write to a `.part` temp and atomically `replace()` into place, so an interrupted write never
leaves a truncated file at the real path — **and** make the "already saved" check verify the
parquet actually reads, not merely exists, so any corrupt-by-other-means file is rebuilt on
the next run rather than trusted. Together these make a retry after any mid-build crash
self-healing, which is also the mechanism that lets dec. #25's empty-title isolation recover
cleanly.

## 31. P18 download-truncation guard was already built — spec ⚠ struck, test kept green

*Ratified 2026-07-06 (v1 Test-Build reconciliation; mirrors the v0 §8.3 assertion-review
record). A spec-vs-code fix, not a runtime-behavior change.*

`TEST_SPEC.md` §v1.1/§v1.5/§v1.7 listed **P18** (the download Content-Length truncation guard)
among the design-anchored ⚠ items to author blind and commit red-first. On building the suite,
P18 came up **green against today's code**: the guard is already implemented at
`scripts/fetch_quarters.py:115` — `_download` streams to a `.part` temp, compares bytes received
against the `Content-Length` header, and on a mismatch unlinks the temp and raises `RunwayError`,
so no file is ever left at `dest`. Marking it ⚠ (xfail-strict) would make the test **xpass** and
fail the suite.

**Why this is a reconciliation, not a miss:** the ratified red-first set is
{A,B,C,E,G,H} = {P12,P4,P13,P14,P15,P16} (`RATIFICATION_LOG_v1.md`, Sitting 2), which never
included D/P18; and call D's reveal reads *"mock the Content-Length guard"* = **test existing
behavior**, not build-new. The ⚠ tag on the P18 row was the inconsistency.

**Resolved:** P18's ⚠ marker is struck in `TEST_SPEC.md` §v1.1/§v1.5/§v1.7; its test
(`tests/test_v1_fetch.py::test_P18_download_truncation_guard_raises_and_leaves_no_file`) stays a
plain **green** pin — not xfail. **Checkable:** the guard is `fetch_quarters.py:115`; the test
asserts `RunwayError` + `not dest.exists()` + no `.part` residue and passes against today's code
(so it can never xpass). This leaves the red-first set at exactly 13 ⚠ tests (0 xpassed).

## 32. v1 finish-build: MUST set driven to green; three SHOULD ⚠ deferred to v1.1 (kept xfail)

*Ratified 2026-07-06 (v1 finish-build; ownership record in `RATIFICATION_LOG_v1.md`, Sitting 3).*

The v1 Test Build committed 13 design-anchored ⚠ tests red-first (xfail-strict). This pass drove
the **MUST** set — P4/Q3 (#27), P12 (#25), P13 (#26), P14 (#28), P15/Q5 (#29), P16 (#30) — to
green, removing each marker as its behavior landed. The three **SHOULD** items below are
**deferred to v1.1** with their xfail-strict markers **kept** — a deferral is logged, never a
silent skip or a deleted/flipped test, so v1.1 inherits an executable to-do. None guards a
correctness invariant, which is why deferring is safe:

- **P20 / call J — `discover_quarters` case-only label collision** (`engine/sponsors.py:101`).
  *Pins:* two parquet whose names differ only in case map to one FY label and one is silently
  dropped. *Deferred because:* (a) it is CI/Linux-only — a case-insensitive filesystem (the
  owner's Windows target) cannot even create the collision; (b) call J left a real **design fork**
  open (deterministic tie-break *vs.* hard error) that deserves a full `/ratify`, not a rushed
  pick; (c) it is the only item that edits a **v0 engine** file, so it must clear P17 deliberately.
  The test asserts the hard-error branch (xfail).

- **P21 / call I — `quarters_superseded` manifest field always `{}`** (`build_shortlists.py:88,73`).
  *Pins:* build_all discards the real superseded map, so the manifest never reports a same-FY
  collapse. *Deferred because:* it **surfaces provenance only** — it does NOT guard the
  cumulative-FYTD double-count / repeat-sponsor invariant, which is enforced upstream by
  `supersede_cumulative_quarters` inside `build_sponsor_table` (the shortlist is already correct;
  only the artifact's transparency field is empty). Triage low/low/low.

- **P19 / call K — `git push` non-fast-forward has no rebase-or-retry** (`scripts/run_pipeline.py`).
  *Pins:* a rejected push should rebase and retry (`push_with_retry(push, rebase)` + a
  `NonFastForward` exception), never silently discard a run's regenerated data. *Deferred because:*
  the `concurrency` group already serializes runs (a race is unlikely) and the worst case is one
  run's data waiting ~a week for the next scheduled run — no data loss, every output is
  regenerable. The orchestrator seam (`run_pipeline.py`, dec. #28) now exists for it to land into.

**Invariant kept:** `python -m pytest` is green with exactly these 3 xfail-strict markers (0
xpassed); v0's suite (95) is untouched (P17). v1.1 drives these 3 to green and removes their markers.

## 33. v1 data path: the converged Build Plan supersedes the scheduled-fetch/parquet slice

*Ratified 2026-07-06. Supersedes dec. #22–#32 (the abandoned slice) as the v1 data path; the
authority is now the Notion v1 Design Doc (D3/D9/§4.2) + Build Plan.*

**What happened.** The v1 data work was first built as a **scheduled automated pipeline slice** —
`fetch_quarters.py` (weekly-cron HEAD-probe discovery + prune), `build_shortlists.py` (per-title
**parquet** + `index.json` manifest, incremental), `run_pipeline.py`, `data-pipeline.yml`, with its
own `TEST_SPEC.md` §"v1 slice" and dec. #22–#32. That slice was built ahead of a compiled Build
Plan; when the Build Plan was generated from the v1 Design Doc it **converged on a simpler, different
architecture**, and the slice diverged from that authority as production code.

**The pivot (this decision).** Adopt the converged plan; delete the slice. Concretely:
- **Output is JSON, not parquet.** The static GitHub Pages site `fetch()`es `web/data/design.json`
  directly; a shortlist parquet would need an in-browser WASM reader for no benefit. Parquet stays
  **only** as the transient xlsx→quarter intermediate (`data/processed/`, dec. #6 — cheap
  re-derivation of a new title), never as the shortlist output.
- **Trigger is `workflow_dispatch`, not cron.** DOL data changes ~4×/yr; the Design Doc (§4.1)
  chose manual dispatch + push-on-code-change. The HEAD-probe discovery / lookback-window / prune /
  per-title-manifest machinery is heavier than v1 needs and is dropped.
- **`build_shortlist.py` (singular) reshaped** to emit `web/data/{design.json (§4.2 closed schema),
  design.provenance.json, design.csv}` in one job with the §4.3 same-generation guard;
  `build_report.py` **deleted** (D3, HTML report retired); `_util.py` repointed to `web/data/`, the
  `output/` tree retired (D9).
- **dec. #23 REVERTED.** Processed parquet is no longer committed — it is gitignored, CI-ephemeral
  (Design Doc §8); the committed/served artifact is `web/data/` (small, diffable JSON/CSV).

**What the slice bought (not wasted):** it affirmed the deterministic path end-to-end — convert +
engine (filter/aggregate/supersede/verify) + orchestrated commit all run — which is exactly the "the
part that doesn't change much works" checkpoint the owner wanted before the UI. dec. #22–#32 remain
as history (why we pivoted); they are not the v1 data path.

**Checkable:** `python scripts/run.py` writes `web/data/design.json` matching §4.2 (verified:
76 employers / 95 filings, golden anchor fires iGavel=7 on FY2025Q4); `scripts/fetch_quarters.py`,
`scripts/build_shortlists.py`, `scripts/run_pipeline.py`, `.github/workflows/data-pipeline.yml`
no longer exist; `build_shortlist.py` has the JSON emit + same-gen guard at its `build()`.

## 34. The caveats-parity build check runs inside `scripts/run.py` (the local build command)

*Ratified 2026-07-08 (v1 Increment 2 close-out). Names the script that runs the check the
Increment-2 spec required to be decision-logged.*

Increment 2 grew the prompt template `prompts/recommendations.md` (dec. #33 / Design Doc D5) —
a repo file the static site fetches and interpolates, so its embedded five caveats reach an
applicant **without ever passing through the engine**. That makes it the one tolerated second
copy of `_util.CAVEATS` (the single source, Design Doc §7). `scripts/check_caveats_parity.py`
asserts the two are byte-for-byte identical (same strings, same order) and raises a plain-English
`RunwayError` naming the first divergence on drift. The open question this decision closes is
*which script actually runs that check* so it guards something instead of sitting idle.

**Alternatives:** (A) wire it into `scripts/run.py`, the one end-to-end local build command;
(B) leave it standalone and call it only from the Increment-5 CI workflow (which doesn't exist
yet); (C) enforce it only through the test suite.

**Why run.py (A), plus a suite pin:** `run.py` is "THE local command" (its own docstring) — the
single thing a maintainer runs to regenerate the site's data input. Making it also assert the
prompt template's caveats keeps *both* of the site's inputs — the data (`web/data/design.json`)
and the template (`recommendations.md`) — consistent with the engine from one command, so drift
can't ship silently between a data regen and a template edit. The check is placed **first**, before
the multi-minute xlsx convert, because it has no data dependency and should fail fast rather than
after expensive work. CI-only (B) was rejected because the workflow isn't built and local runs would
be unguarded until it is; test-only (C) is kept as a complement, not the sole path — a build check
belongs in the build. So the check runs in **two** places that can't disagree: `run.py` at build
time, and `tests/test_caveats_parity.py` in the green suite (a positive pin that the real repo
files match, plus a negative test that an injected drift raises `RunwayError`).

**Checkable:** `scripts/run.py` imports `check_caveats_parity` and calls it before `convert_all`;
`python scripts/check_caveats_parity.py` prints `[caveats-parity] OK - 5 caveats match`;
`tests/test_caveats_parity.py` passes (positive + negative). Closes Increment 2 alongside the
deletion of the superseded `prompts/gap_read.md`.

## 35. The prompt template is build-mirrored into `web/prompts/` so the site can fetch it from the `web/` serve root

*Increment 3 (2026-07-17). Resolves a contradiction discovered in the Design Doc, not a scope
addition — flip it if the owner prefers a different reconciliation.*

**The contradiction.** Design Doc §5.4 has the site fetch `prompts/recommendations.md`, and
§13.3 (OI-2, explicitly resolved) serves the site with `python -m http.server` **rooted at
`web/`** — from which the repo-root `prompts/` directory is unreachable (an HTTP server never
serves above its root, and `../` normalizes away in URLs). As written, the local end-to-end leg
of the Definition of Done could never reach the template. The same hole would hit the Pages
deploy if the published artifact is `web/` (Increment 5's likely shape).

**Resolution.** `scripts/run.py` copies `prompts/recommendations.md` byte-for-byte to
`web/prompts/recommendations.md` (`mirror_prompt_template()`, placed immediately after the
caveats-parity check so the mirror is always a parity-verified template, and before the convert
step because it is data-independent). The mirror is a **committed build artifact** exactly like
`web/data/*`: the single source of truth stays the repo-root file (D5 intact), the mirror is
regenerated on every build and never hand-edited, and `app.js` fetches the literal path
`prompts/recommendations.md` — which now resolves *inside* the serve root, satisfying §5.4's
fetch path and §13.3's serve command simultaneously.

**Alternatives rejected:** serving from the repo root (contradicts the explicitly-ratified
OI-2, and would force the Pages artifact to be the whole repo); a hand-committed duplicate
(drift risk with no build guarantee — the caveats-parity lesson); moving the template into
`web/` outright (breaks the §8 repo layout and D5's stated path).

**Checkable:** `git diff --no-index prompts/recommendations.md web/prompts/recommendations.md`
is empty; deleting the mirror and running `scripts/run.py` recreates it; with
`python -m http.server` rooted at `web/`, `GET /prompts/recommendations.md` returns 200.

## 36. `{{SELECTED_ROWS}}` renders as CSV: design.csv's exact columns and order, RFC 4180-quoted, null wage → empty cell

*Increment 3 (2026-07-17). The rendering choice the increment spec requires to be logged.*

The selected shortlist rows are interpolated into the prompt as **CSV**: one header line plus
one line per selected employer, using **exactly the 13 `design.csv` columns in `design.csv`
order** (`CSV_COLUMNS` in `web/app.js`). Why CSV over prose or JSON: the LLM receives the same
representation a human can cross-check against the public `web/data/design.csv` download —
line-for-line — so "which facts were sent" is auditable by diffing, and the template's §6.1
framing ("filing counts, wage levels, SOC titles, worksite states are facts") points at flat
tabular fields, not a nested object.

Field rules (`csvField` in `app.js`): RFC 4180 — a field containing a comma, quote, or newline
is double-quoted with inner quotes doubled (so `iGavel, Inc.` round-trips); a `null` wage
becomes an **empty cell**, matching the emitter's convention for `design.csv` (v0 F5: blank,
never `"nan"`, and never a fake zero). Interpolation uses `split()/join()`, not
`String.replace()`, because a pasted résumé may legitimately contain `$&`-style sequences that
`replace()` would treat as substitution patterns.

**Checkable:** select iGavel in the served site → the generated prompt contains the line
`IGAVEL,"iGavel, Inc.",7,1,FY2025Q4,no,27-1024,Graphic Designers,TX,New Braunfels,40250,40250,40250`,
identical to that employer's `web/data/design.csv` line.

## 37. A null median wage renders as an em dash (—) in the shortlist table

*Increment 3 (2026-07-17). The null-rendering choice the increment spec requires to be logged.*

A wage excluded from wage stats arrives in `design.json` as JSON `null` (§4.2, the v0 F5
lesson). In the shortlist table it renders as an **em dash "—"** — visibly *absent*, never `$0`
(a lie), an empty cell (reads as a rendering bug), or the string "null"/"nan". The em dash is
produced in `renderRow` in `web/app.js` (`wage_annual_median == null ? "—" : …`); the same
employer's `{{SELECTED_ROWS}}` CSV line keeps the empty-cell convention instead (dec. #36) —
display shows absence to a human, data stays machine-parseable.

**Checkable:** in `web/app.js` `renderRow`, the median-wage branch; live, no current row is
null-waged, so: `renderRow({wage_annual_median: null, …}).cells[7].textContent === "—"` in the
browser console (verified in the Increment-3 build pass).

## 38. Portfolio "validated as a URL" = the URL constructor + an http(s) scheme, with no silent rewriting

*Increment 3 (2026-07-17). Names the concrete meaning of §5.2's "validated as a URL".*

A portfolio link counts as present when `new URL(value)` parses it **and** its protocol is
`https:` or `http:` (`portfolioUrl()` in `web/app.js`). Anything else — including a bare
`myname.com` — shows the inline hint "Enter a full link starting with https:// (or http://)"
and keeps Generate disabled. Deliberately **no auto-prefixing**: what the user typed is exactly
what enters the prompt (`{{PORTFOLIO}}`), so Runway never fabricates even a scheme on the
user's behalf — the same honesty rule the data side follows. Non-http schemes (`javascript:`,
`file:`) are rejected rather than forwarded into a prompt the user will paste elsewhere.

**Checkable:** in the served site, `myname.com` in the portfolio field keeps Generate disabled
and shows the hint; `https://myname.com` enables it once ≥1 company is checked.

## 39. "UI/UX Design" is a second, narrower registered role — a subset view of "design", not a rename

*2026-07-20, off-plan (owner: "my plan supersedes the Build Plan").*

**Alternatives:** (a) just relabel the existing "design" dropdown entry to "UI/UX Design"; (b)
narrow `ROLE_SOC["design"]` itself to only `15-1255` and rename it; (c) register a second,
independent role.

**Why (c):** the "design" role's 3 SOC codes (`15-1255` Web and Digital Interface Designers,
`27-1024` Graphic Designers, `27-1021` Commercial/Industrial Designers, dec. #3) are broader
than "UI/UX" — relabeling in place (a) would misdescribe graphic/industrial-design filings as
UI/UX. Narrowing "design" itself (b) would silently shrink an existing shortlist. Instead
"design" is untouched and a second role, `"uiux": ["15-1255"]`, is registered alongside it in
`engine.ROLE_SOC` — two distinct dropdown entries, two distinct `web/data/*.json` shortlists,
no company appears under a role it doesn't belong to.

No SOC/O*NET code is scoped to "UI/UX" specifically — `15-1255` (Web and Digital Interface
Designers) is the closest official match and what "UI/UX" colloquially means, so `uiux` reuses
it verbatim rather than inventing a code. Per dec. #3's amendment, matching is by base code, so
`uiux` also pulls in `15-1255`'s detail-suffix family (in practice: Video Game Designers,
`15-1255.01`) — the same consequence "design" already has for that code, now owned explicitly
for the narrower role too.

This required generalizing the previously design-only `scripts/build_shortlist.py` (single
`ROLE`/`JSON_PATH`/`PROVENANCE_PATH`/`CSV_PATH` constants) to a `build(role, ...)` that computes
`web/data/<role>.{json,provenance.json,csv}` per role, plus `build_all()` which builds every
key in `ROLE_SOC` — so a third role later is a registry entry, not another script rewrite.
`scripts/run.py` now calls `build_all()`. The frontend SOC-titles column additionally annotates
`Web and Digital Interface Designers` rows with "(UI/UX)" (`web/app.js` `renderRow`) so the
official SOC title is legible against the colloquial term, in both roles' shortlists — display
only, the underlying `soc_titles` data stays the DOL title verbatim.

**Checkable:** `engine.sponsors.ROLE_SOC["uiux"] == ["15-1255"]`; after `python scripts/run.py`,
`web/data/uiux.json` exists with `"role": "uiux"` and every employer's `soc_codes` contains only
`15-1255`; `web/data/design.json` is unchanged (same `employer_groups` count as before this
decision, since `ROLE_SOC["design"]` wasn't touched).

## 40. The résumé input is a file path string, not pasted résumé text

*2026-07-20, off-plan (owner: "resume should be a filepath").*

**Alternatives:** (a) keep the pasted-text textarea (the original Increment-3 shape — Runway
"reads no user file", so the applicant pastes the content themselves); (b) add real file upload
(`<input type="file">` + `FileReader`) so the browser reads the résumé and its text is what
fills the prompt.

**Why neither:** (a) required the applicant to copy their résumé's text out of whatever authored
it (Word, a PDF export, Google Docs) and into a browser textarea before every run — friction for
no benefit once the target audience is "an applicant who may run this prompt through an agent
with file access," not only a plain chat window. (b) would make Runway read a user's file for the
first time, reversing the site's one deliberate boundary ("Runway never reads a user's file",
README, `index.html` §5.2 comment) to save the applicant a few keystrokes — not worth it.

**Resolved:** `#resume-input` is a plain text field for a file path (e.g.
`/Users/you/Documents/resume.pdf`); `{{RESUME_OR_NONE}}` is filled with that path string
verbatim, or `"none provided"`. Runway's own code never opens, reads, or validates the path —
identical posture to the portfolio link (dec. #38): what the user typed is exactly what enters
the prompt, no existence check, no silent rewriting. What happens with the path is up to whatever
runs the prompt: an agent with file access can read it; a plain chat LLM just sees a string and is
told (via `prompts/recommendations.md` §2) to proceed on the portfolio and shortlist alone if it
can't resolve it.

**Checkable:** in the served site, typing `/tmp/resume.pdf` into the résumé field and generating a
prompt puts the literal text `/tmp/resume.pdf` in the `{{RESUME_OR_NONE}}` slot; leaving it blank
puts `none provided`. `web/app.js` has no `FileReader`, no `<input type="file">`, no `fetch` of
the path.

## 41. PromptReady requires a portfolio link OR a résumé path, not portfolio specifically

*2026-07-20, off-plan (owner: "doesnt need to mandate portfolio... resume or portfolio is
required... to care for future titles").*

**Alternatives:** (a) keep portfolio mandatory (Increment 3's original shape, dec. #38) now that
a résumé path (dec. #40) is a second, comparably substantive input; (b) require both.

**Why neither:** (a) makes no sense once the résumé field went from "reference only" (pasted
text used solely to enrich the prompt) to a real second input path — an applicant with a strong
résumé but no public portfolio (a real case for a future non-Design role, e.g. one where a
portfolio link isn't the norm) had no way to reach Generate. (b) is stricter than the actual
requirement: the prompt is useful with just one input, and a hard AND would block the same
future-role case for the opposite reason.

**Resolved:** PromptReady is now `>= 1 company selected AND (a valid portfolio URL OR a non-empty
résumé path)`. Neither input is individually required; a portfolio value that's present but
fails URL validation (dec. #38) still blocks Generate and shows the inline hint — that's a typo
to fix, not a missing-input case, so it's kept strict. `web/index.html` §2 carries one explanatory
note above both fields ("add at least one... both gives more to work with") rather than
repeating the rule on each label. `{{PORTFOLIO}}` now has a fallback fill
(`"no portfolio link provided"`) mirroring `{{RESUME_OR_NONE}}`'s `"none provided"`, and
`prompts/recommendations.md` §"Inputs" tells the reviewer to work from whichever of the two is
present rather than assuming both.

**Checkable:** in the served site, leaving portfolio blank and only filling résumé path + selecting
a company enables Generate; the resulting prompt's portfolio slot reads
"no portfolio link provided". Typing a non-URL string (e.g. `not a url`) into portfolio with an
empty résumé keeps Generate disabled and shows the inline "Enter a full link..." hint — it does
NOT fall through to treating that as "portfolio absent."

## 42. `web/app.js` gets a narrow, deliberately incomplete automated test suite

*2026-07-20, owner call after "what do you think needs to be tested?"*

**Alternatives:** (a) no automated JS tests at all — keep relying on a manual `/browse` pass
after each change (what every prior UI increment did); (b) full coverage — sort, CSV
serialization, DOM rendering, load/error states; (c) the narrow slice actually chosen.

**Why (c):** Runway's web UI is static, single-user, no backend, no auth, no persistence — the
worst failure mode of a UI bug is "the copied prompt is wrong or empty," not data loss or a
breach. That ruled out (b): sort order, CSV formatting, and rendering details are cheap to get
wrong but cheap for the user to notice and fix by re-copying, so testing them is a maintenance
tax without a matching risk. It also ruled out (a) for exactly three spots that don't fit that
"low stakes, user notices" profile:

- **Escaping** (the v0 M13 lesson, carried into every DOL-sourced field in `renderRow`): a
  regression here is a real client-side injection risk, not a cosmetic one, and the fix (swap
  `textContent` for `innerHTML` "to allow some formatting") is exactly the kind of change that
  looks harmless in review.
- **Portfolio URL scheme validation** (`isValidPortfolioUrl`, dec. #38): blocks `javascript:`/
  `data:` values from ever reaching the field — also security-relevant, also a one-line
  regression risk.
- **The `computePromptGate` branch logic** (dec. #41): ~6-8 states across two optional-but-
  not-both-optional inputs, added the same day this decision was made — exactly the shape of
  logic that silently breaks on a future one-line "fix" to a single branch.

**Resolved:** added `vitest` + `jsdom` as dev-only dependencies (`package.json`), a
`vitest.config.js` (jsdom environment, `web/**/*.test.js`), and `web/app.test.js` (17 cases).
Required extracting two pure functions out of DOM-coupled ones so they're testable without a
full page: `isValidPortfolioUrl(raw)` out of `portfolioUrl()`, and `computePromptGate({...})` out
of `updatePromptGate()` — same behavior, DOM reads/writes now wrap the pure call instead of
containing the branch logic. `renderRow` was already DOM-fragment-only (`document.createElement`,
no full-page dependency), so it's tested directly. `web/app.js` is now an ES module (`export` on
`state`/`isValidPortfolioUrl`/`computePromptGate`/`renderRow`; `index.html`'s `<script>` tag
gained `type="module"`) and its bottom event-wiring block is guarded on `$("title-select")`
existing, so importing the module in a test (no full DOM loaded) doesn't throw. Both changes are
behavior-preserving on the served page — confirmed via `/browse` (role load, sort, prompt
generation all unchanged, no console errors).

**Checkable:** `npm test` runs `vitest run`; `npm run dev` still serves and behaves identically.
`web/app.test.js`'s "does not fall through to the OR message when portfolio text is present but
invalid" case is the regression pin for dec. #41's most subtle branch.

## 43. Automated fetch is restored — the pipeline discovers + downloads new DOL quarters on its own (partially reverses dec. #33)

*2026-07-21, owner call: "the data pipeline should be checking for a new quarter and downloading
if there is one." Pulls Increment 5 (CI + deploy) ahead of Increment 4 (results render); the
owner ratified both the reversal and the reordering (AskUserQuestion, this session).*

**What changed.** dec. #33 deleted the scheduled-fetch slice (`fetch_quarters.py` +
`data-pipeline.yml`) and chose a **manual `workflow_dispatch`** trigger, judging the HEAD-probe
discovery machinery "heavier than v1 needs." The owner now wants the pipeline to check for new
quarters *without a human pushing a button*. This restores automated fetch and re-adds the weekly
`schedule:` — the one part of dec. #33 that is reversed. Everything else dec. #33 settled stands:
output is still JSON in `web/data/` (not parquet), processed parquet is still gitignored/ephemeral
(dec. #23 stays reverted), and the engine + `convert_quarters.py` are untouched.

**What was restored, not rewritten.** `scripts/fetch_quarters.py` and its tests
(`tests/test_v1_fetch.py`, `tests/v1_support.py`) are recovered from git (`7198e0b^`, the commit
that deleted them) — the same HEAD-probe discovery, `.part`-temp truncation guard, and
conservative prune (dec. #27: prune only on supersession or out-of-window, never a probe-miss),
which still tie cleanly to today's `engine.sponsors.discover_quarters`. The deleted slice's
`build_shortlists.py`/`run_pipeline.py`/`index.json` machinery is **not** restored — dec. #33
retired it. The recovered P20 case (a `discover_quarters` case-collision guard) is **dropped**: it
was deferred to v1.1 and edits a v0 engine file, out of scope for this restore.

**How it wires in.**
- `scripts/run.py` gains a fetch step (before convert) and a `--no-fetch` escape hatch for offline
  work / a manually-dropped xlsx. A bare `python scripts/run.py` now checks DOL first.
- `.github/workflows/data-pipeline.yml`: weekly `schedule:` (`17 6 * * 1`) + `workflow_dispatch`,
  serialized by a concurrency group, `contents: write`. It runs **fetch as its own gated step**
  (`id: fetch` → `changed`), then runs `run.py --no-fetch` and commits `web/data/` **only when
  `changed == 'true'`**. The gate matters because `build_shortlist` stamps `generated_at_utc` every
  run — an ungated rebuild would commit a timestamp-only diff every week; gating keeps the ~51/52
  no-quarter runs genuinely no-op (a few HEAD probes, nothing committed).
- The workflow **caches `data/processed/`** (gitignored, ephemeral) so fetch's "do I already have
  this quarter?" check has state across runs — on a no-new-quarter run it HEAD-probes and downloads
  nothing, courteous to DOL's endpoint. Pure optimization: a cache miss just re-downloads (a
  possible one-off timestamp-only commit before it self-heals), never a correctness issue.

**Verified (2026-07-21):** the URL template still resolves — HEAD probes return 200 for FY2025 Q3/Q4
and FY2026 Q1, 404 for FY2026 Q2 (not published). The real discovery path (`discover_upstream`, HEAD
only, no download) run against live DOL returns exactly `{FY2025Q4, FY2026Q1}` — the golden-anchor
window. Suite: 96 passed (14 restored fetch cases green, no prior test regressed). The real *download*
+ end-to-end run stays out of the suite (ratified SK-v1-1: Scenario C, the first scheduled CI run).

**Deferred (unchanged from the original slice):** rebase-or-retry on a non-fast-forward push
(old P19) — safe to skip because the concurrency group serializes runs; a v1.1 hardening.

## 44. Title-shortlist patterns are pre-computed deterministically in the engine, not left to the user's LLM

*2026-07-21, owner call ("the pre-processed patterns are viable as an immediate extension to the
data pipeline per title"); the four design knobs below were each ratified in-conversation before
the build.*

**The problem.** The recommendations prompt asks the user's own LLM to surface, for a job title,
"patterns in the roles and skills that sponsors hire for" and one project to build toward them. An
LLM asked to *count* over the shortlist rows (36 filings / ~29 employers for `uiux` across two
quarters) miscounts subtly — fatal to the product's trust claim — and would burn user tokens doing
arithmetic badly. So the counting moves into the deterministic engine; the user's LLM keeps only
the *interpretation* (which project, how to frame it), which is where flexibility and the teaching
value actually live.

**Alternatives considered.** (a) Leave all pattern-finding to the user's pasted prompt — rejected:
the miscount risk above, and no denominator discipline. (b) Call an LLM at build time to write
pattern *prose* into the JSON — rejected: breaks the architecture's load-bearing line ("Runway
never calls an LLM") and hides the very reasoning the prompt exists to teach. (c) Pre-compute the
*counts* only, in the engine, and hand them to the user's LLM as stated facts — **taken.** The
arithmetic has one correct answer and no flexibility to lose; the interpretation stays with the
user.

**What was built.** `engine.sponsors.compute_patterns(selected)` runs over the already-selected
title-shortlist rows (certified ∩ Level I ∩ role SOCs ∩ quarters on disk) and returns a
`patterns` object now carried in both `web/data/<role>.json` and its provenance. Blocks:
`job_titles.recurring_tokens` (floor-gated), `job_titles.distinct_titles` (verbatim evidence),
`onet_occupations`, `placement_model`, `industry_naics2`. Two columns were added to
`REQUIRED_COLUMNS` — `NAICS_CODE` and `SECONDARY_ENTITY` — read *only* as pattern inputs; neither
touches the certified/SOC/wage filter or the employer aggregation. Adding them makes every
pre-#44 parquet stale, which the engine's existing missing-column guard catches loudly
(`--force-convert` to rebuild); the CI cache key was bumped `dol-processed-v1-`→`-v2-` so the
scheduled run re-fetches to the 14-column schema instead of tripping that guard.

**The four ratified knobs (the judgment calls):**
1. **Denominator is employers, not filings.** Every count carries both, but the support floor and
   all "which pattern is real" logic count *distinct employers* — so one prolific filer cannot
   manufacture a pattern.
2. **Support floor = 3 employers.** A recurring token or industry sector below it is **dropped
   entirely, not hedged** (~10% at real Level-I design volume). Revisit only if a real pull looks
   too sparse. (This also gives a clean rule for admitting new title patterns automatically.)
3. **Tokenizer strips only non-discriminating words** — the role-family words (`design`/`designer`,
   true of ~100% of rows *by construction* so zero-signal here) plus articles and bare
   numerals/roman markers. Seniority (`senior`/`lead`/`founding`) and domain words
   (`product`/`web`/`ux`) are kept — they are the signal. Because bag-of-words alone destroys title
   legibility, `distinct_titles` ships the **verbatim** titles alongside (employer-counted, no
   floor, no stopword): the tokens are the finding, the raw titles are the evidence.
4. **The O*NET split is presentation-only.** `canonical_onet()` preserves the decimal suffix that
   `normalize_soc()` strips for matching, so `15-1255.01` (Video Game Designers) shows as a distinct
   line instead of silently inflating the base occupation. Matching and dec. #39 are unchanged.

**Naming.** The pre-selection row set is called the **title-shortlist** (or "matched filings"),
never "cohort" — it is a convenience sample of *filings*, not a representative sample of an
industry, and the flatter name keeps that honest. Patterns computed on it; the user's *selection*
of specific companies only shades the resulting project, never generates it.

**Checkable.** `web/data/design.json` and `uiux.json` carry a top-level `patterns` object;
`engine.verify.check_patterns_consistent` fails the build if a floor-gated entry leaks below the
floor, any bucket exceeds the basis, or `basis.employers != employer_groups`; the emit's
same-generation guard now also pins `patterns.basis.employers`. Suite: 115 passed (+19 over dec.
#43's 96 — engine unit tests for the tokenizer/O*NET/floor/denominator knobs, an emit oracle for
the whole `patterns` object, and property I9). The prompt-template rewrite that *consumes* this
block (the §1–§5 output structure) is the next slice, not this one.
