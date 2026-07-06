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
