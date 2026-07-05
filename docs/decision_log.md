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
