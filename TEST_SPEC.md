# Runway — Test Spec

`test-spec v0.2.0 · 2026-07-02, amended 2026-07-04, 2026-07-06` — **v0 ratified 2026-07-02**
through item-by-item dialogue; **amended 2026-07-04** to reconcile the §8.3 fresh-context
assertion review after the automated suite was built (see §8.3); **v1 data-pipeline slice
appended + ratified 2026-07-06** (see §"v1 — Data-pipeline slice"; ownership record in
`RATIFICATION_LOG_v1.md`, Sitting 2).
Living document: amend as the design evolves; do not clobber. The diff history is the record
of what changed about what-must-be-true. Sections §1–§8 below are the **v0** spec (full
pipeline); the **v1 slice** at the end covers the data-pipeline rebuild and reuses v0's
engine coverage at the seams rather than duplicating it.

---

## 1. Orientation

**Under test:** Runway v0 — the full pipeline (conversion → engine → verify → shortlist →
report → CLI error contract), per the ratified scope decision.

**Design authority:** the canonical [Design Doc](https://app.notion.com/p/Design-Doc-39076356d6fe8172989bfe796954eed8)
(Notion, "§n" below) and `docs/decision_log.md` ("dec. #n"). Code symbols are cited where the
behavior lives. Items the design never stated are tagged **[ratified-in-test-spec]** — they were
decided during this spec's dialogue and the design doc / decision log must be amended to match
(see §5, *Design amendments owed*).

**Acceptance statement:** Runway v0 is trusted to ship when the automated suite is green on
synthetic fixtures, **and** the golden real-data run (Scenario A) plus the failure-face run
(Scenario B) pass on the target JP-locale Windows machine, **and** the human pass (spot-trace +
real-user read) is done. A green suite alone is not the gate.

**Where the risk concentrates (ratified):**
1. **The filter funnel** — certified/SOC/wage-level normalization; a silent mis-filter produces a
   confidently wrong shortlist, and the product's edge is "every number traces to a DOL filing."
2. **Employer normalization + aggregation** — a false merge points an applicant at a company that
   doesn't exist; dropped/duplicated filings make the counts lie.
3. **The verify layer itself** — the runtime green light; a check that cannot fire is worse than
   no check (§8).
4. **Manual-input handling** — the two human-touch files (`hiring_now.csv`,
   `gap_read_filled.md`) must never be clobbered, must fail in plain English, and must escape
   hostile content.
5. **Quarter arithmetic (added by the adversarial sweep)** — DOL quarterly files are cumulative
   FYTD; naive multi-quarter loading double-counts and fabricates the repeat-sponsor signal (F1).

### Must-test index

⚠ = expected to **fail against today's code** — the test documents ratified behavior the build
must catch up to. That is spec-first working as intended, and doubles as proof the test can fail.

| # | Behavior (one line) | Traces to | Method | Tier |
|---|---|---|---|---|
| M1 | Only exact `Certified` rows pass the status filter | §5; dec. #2; `sponsors.py:174` | unit | MUST |
| M2 | SOC match is by base code; O*NET detail suffixes (.00, .01…) included | dec. #3; `normalize_soc`; F6 **[ratified-in-test-spec]** | unit | MUST (+SHOULD pin for .01) |
| M3 | Wage-level spellings normalize to I–IV; unknown → None; all-None quarter stops | §5; `normalize_wage_level` | unit | MUST |
| M4 | Annualization FROM×{1,2080,12,52}; unparseable wage stays counted, excluded from stats, tallied | dec. #8; `sponsors.py:206` | unit | MUST |
| M5 | Employer key conservative: case/punct/4-suffix only; LLP kept; distinct names never merge | dec. #9; §5; `normalize_employer` | unit + property | MUST |
| M6 | Per-employer row correct: count, display=modal spelling, repeat⇔≥2 quarters, wage stats, sort | dec. #10; `sponsors.py:219-247` | unit | MUST |
| M7 | Funnel monotone; Σ filing_count = rows_selected; groups ≤ raw spellings | §7; `verify.py` | unit + property | MUST |
| M8 | Conversion: columns by name; padding rows dropped **and counted**; label from filename; `~$` ignored; mtime skip + `--force-convert`; misnamed xlsx skipped w/ message (SHOULD) | §5; dec. #6, #7, #16 | fixture | MUST |
| M9 | Every anticipated failure = `RunwayError`, plain English, exit 1, no stack trace | §7; dec. #15; all raise sites | unit + fixture | MUST |
| M10 | `--quarters` = assertion, never selector; extras always used; missing named quarter stops | §5 (gap G1); dec. #11 | unit | MUST |
| M11 | Golden check: FY2025Q4 → top must be IGAVEL; absent → SKIP not fail | dec. #12; `verify.py:100` | unit + real-data gate | MUST |
| M12 | `hiring_now.csv`: created blank once, **never overwritten**; values reach report; stale keys ignored w/o crash; broken columns → instructive error | dec. #4; `build_report.py:42` | fixture | MUST |
| M13 | Gap read: absent → visible placeholder, run succeeds; renderer (headings demoted, lists, bold, links) escapes input; hostile markdown inert incl. ⚠ href-attribute breakout | §3; dec. #17; `markdown_to_html`; J5 | unit | MUST |
| M14 | Report: **every** row (no truncation), 5 caveats verbatim, single-quarter note iff 1 quarter, wage-excluded note iff >0, missing wage → — | §6, §2; dec. #13; `_util.CAVEATS` | unit + fixture | MUST |
| M15 | UTF-8 artifacts; cp932 console never crashes a run | dec. #14; `force_utf8` | fixture + manual | MUST |
| M16 | Provenance JSON complete and consistent with the CSV it accompanies | §7; `build_shortlist.py` | fixture | MUST |
| F1 | ⚠ Overlapping same-FY (cumulative) quarter files must not double-count filings or fabricate repeat_sponsor | sweep; DOL cumulative-FYTD files; **[ratified-in-test-spec — design amendment owed]** | fixture | MUST |
| F2 | ⚠ Non-UTF-8 manual input (cp932-saved csv/md) stops with plain-English error naming the file and fix | sweep; dec. #15 contract; `build_report.py:56,130` | fixture | MUST |
| F3 | ⚠ Unreadable/truncated parquet stops with plain-English error naming `--force-convert` (never sticky-skipped) | sweep; dec. #7, #15; `sponsors.py:140` | fixture | MUST |
| F4 | ⚠ Empty/whitespace `gap_read_filled.md` behaves as absent (placeholder), never a silent blank section | sweep; §3 pending-review contract; `build_report.py:128` | unit | MUST |
| F5 | ⚠ Report-side CSV read round-trips every cell as written: blank renders blank (never "nan"); hiring join on exact strings | sweep; `build_report.py:37 vs :56` | fixture | SHOULD |
| F7 | ⚠ Report build asserts table/provenance are the same generation (`len(table) == employer_groups`) | sweep; `build_report.py:196-232` | unit | note |
| V1–V4 | Each verify check demonstrably **fires** on corrupted input (see §8) | `verify.py` all checks | unit (negative) | MUST |
| P1 | Parquet write→read→compare with unicode, blanks, long strings | promoted from SKIP #3 | unit | SHOULD |
| D1 | README advisory: don't run two invocations concurrently | promoted from SKIP #6 | docs action (no test) | SHOULD |

## 2. What "correct" means — behaviors traced to design

The index rows above are the checkable statements; detail where a wrong call is expensive:

- **M1** Given rows with statuses `Certified`, `Certified - Withdrawn`, `Denied`, `Withdrawn`,
  only exact `Certified` (case/whitespace-cleaned) survives. `Certified - Withdrawn` exclusion is
  deliberate (dec. #2) and must be pinned by an explicit test row.
- **M2/F6** Given `15-1255.00` and `15-1255.01`, both match role `design`. Base-code matching is
  the **ratified intent** (the wage level certifies against the base occupation), decided in this
  spec's dialogue — decision log owes a line. A test pins `.01` inclusion so the scope is chosen,
  not an accident of `split(".")[0]`.
- **M4** Given FROM=`"$85,000.00"`, unit=`HOUR` → annual 176,800,000? No — 85000×2080; the test
  matrix covers each unit, `$`/comma parsing, blank FROM, and `Bi-Weekly` (excluded from stats,
  present in counts, tallied in `rows_wage_excluded`). Dropping such a filing would understate a
  sponsor — the spec forbids it (dec. #8).
- **M5** `Acme Design LLC` ≡ `ACME DESIGN, INC.` ≡ `Acme  Design`; `Deloitte Consulting LLP`
  keeps LLP; `Acme Design` and `Acme Designs` never merge. Under-merge over over-merge, always.
- **M6** Two synthetic quarters exercise `repeat_sponsor` both ways and `quarters_present`;
  display name is the modal raw spelling with deterministic tie-break; sort is
  quarters↓, filings↓, name↑.
- **M12** The tool writes `hiring_now.csv` **only when absent**; a re-run after hand-editing
  leaves every byte of user work intact. Stale keys (shortlist changed) are ignored without
  crash — and the missing staleness *warning* is a logged design observation (§5), not a test.
- **M13** Hostile markdown: `<script>` inert; `javascript:` never linkified; and the
  **href-attribute breakout** (`[x](https://a.com/"onmouseover="…)` — `html.escape(quote=False)`
  leaves `"` live inside `href`) must be impossible. ⚠ Known-failing today; the fix is a
  one-liner at build time.
- **F1** Given two synthetic "quarters" sharing filings (modeling DOL's cumulative FYTD files),
  the pipeline must detect/refuse/dedupe — the *mechanism* is a design decision to log; the
  *invariant* (no filing counted twice, no fabricated repeat signal) is ratified now. Until
  amended, dec. #11's "extra quarters are harmless" and the report's "convert another quarter"
  note are wrong for same-FY files.

## 3. Invariants — property-test candidates

Ratified: **hypothesis** as a dev-only dependency (`requirements-dev.txt`); user-facing install
surface unchanged, honoring the spirit of dec. #17.

| # | Property (falsifiable statement) | Anchors |
|---|---|---|
| I1 | `normalize_employer` is idempotent: `f(f(x)) == f(x)` for arbitrary strings | M5 |
| I2 | `normalize_employer` never merges names differing in a non-suffix token | M5; dec. #9 |
| I3 | `normalize_employer` never raises; empty/punctuation-only input → `""` key; such filings stay counted under one group, rendered as-is (**ratified: no crash, counted, as-is**) | J7 |
| I4 | `normalize_wage_level` is total: any input → {I, II, III, IV, None}, never raises | M3 |
| I5 | Aggregation partitions: every selected filing in exactly one employer group; Σ filing_count = rows_selected | M7; `check_filing_count_sum` |
| I6 | Where wage stats exist: min ≤ median ≤ max | M6 |
| I7 | Funnel monotone: total ≥ certified ≥ SOC-matched ≥ selected | M7 |
| I8 | No filing contributes twice to any count across loaded quarters (⚠ violated today by cumulative same-FY files — F1) | F1 |

## 4. Failure modes & edge cases — triaged

Scored likelihood / blast / cost → tier. Every SKIP is deliberate and logged.

| Case | L / B / C | Tier | Where |
|---|---|---|---|
| PERM file dropped in `data/raw/` | med / high / low | MUST | M9 (named suspicion in message) |
| Empty `data/raw/` on first run | high / low / low | MUST | M9 + Scenario B |
| Requested quarter not converted | med / med / low | MUST | M10 |
| Same-FY cumulative overlap double-count | **high** (report suggests it!) / **high** / med | MUST ⚠ | F1 |
| cp932-saved manual inputs → traceback | **high on target machine** / med / low | MUST ⚠ | F2 |
| Truncated parquet sticky-poisons every run | med / med / low | MUST ⚠ | F3 |
| Empty gap-read file blanks flagship section | med / med / low | MUST ⚠ | F4 |
| Hostile gap-read markdown (incl. href breakout) | low / med / low | MUST ⚠ | M13/J5 |
| Blank employer name → empty-key row | very low / low / ~0 | property, as-is | I3/J7 |
| Stale `hiring_now.csv` after shortlist change | med / low / low | tested-as-designed; warning gap → design observation | M12/J4 |
| CSV type-inference mutations ("nan", broken join) | low / med / low | SHOULD ⚠ | F5 |
| Corrupt xlsx (bad download) | med / low / low | SHOULD | M9 |
| Misnamed xlsx silently unconverted | med / low / low | SHOULD | M8 |
| Mixed-generation CSV/provenance pair | very low / med / ~0 | note | F7 |

### The SKIP list (ratified — considered and deliberately not tested, because…)

| Skip | Reason |
|---|---|
| S1 Perf/memory of the 100 MB stream | Regression unlikely; blast is minutes not wrongness; CI cost high. Observed incidentally in Scenario A. |
| S2 HTML visual appearance | Cosmetic; the human acceptance pass eyeballs the real report — that's the reserved human layer's job. |
| S4 Multi-sheet xlsx | DOL publishes single-sheet; a decoy first sheet fails loudly via the required-columns check (M9). We rely on that check and say so. |
| S5 Ctrl-C exit code (130) | Trivial plumbing; signal tests flaky on Windows. **The dangerous consequence of Ctrl-C — the truncated parquet — was promoted to F3 (MUST); only the exit-code cosmetics are skipped.** |
| S6 Concurrent runs | Single-operator CLI by design; corrupts only regenerable artifacts. Demoted to D1 README advisory (a docs action, not coverage). |
| S3 Parquet round-trip | ~~skip~~ **promoted to P1 (SHOULD)** during ratification. |

## 5. Out of scope

- **Writing/running the tests** — this document specifies; a separate build step implements.
- **Layer A / v2 features** (postings, classification, UI, more roles) — design §8.
- **Gap-read content quality** — Layer 3 is human-reviewed *by design*; the spec tests the
  plumbing (placeholder, rendering, escaping), never the judgment.
- **Immigration accuracy of caveat wording** — ratified in design §9; tests assert verbatim
  presence only.
- **Decision-log entries that are process, not runtime behavior** (#1 source choice, #5
  architecture split). The engine's no-LLM/no-HTML property is enforced structurally and by
  review, not by tests.

### Design amendments owed (recorded here so silence ≠ oversight)

1. ~~**F1:** Design §5/§6, dec. #11, and the report's "convert another quarter" note must be
   amended for DOL's cumulative-FYTD reality; the dedupe/refuse/warn mechanism is a fork to log.~~
   **STRUCK 2026-07-04 (dec. #21):** mechanism ratified = **supersede** to the latest same-FY
   file. dec. #10 and dec. #11 amended inline; the report note now points at fiscal years;
   `quarters_superseded` announced on console + in provenance. *Remaining external action:*
   update the Notion Design Doc §5/§6 for cumulative-FYTD reality (routes to Notion per the
   recording standard, not an in-repo edit).
2. **F6:** dec. #3 gains a line: base-SOC matching includes O*NET detail suffixes (ratified).
3. **J4:** no staleness warning exists for `hiring_now.csv` after the shortlist changes —
   observation for the design doc's next revision, not silently absorbed.

## 6. Verification plan — method per item

| Method | Items | Automated? |
|---|---|---|
| **unit** (pytest, synthetic frames) | M1–M7, M9(engine raises), M10, M11(synthetic), M13, M14, M15(`force_utf8`), F4, F7, V1–V4 | yes |
| **property** (hypothesis, dev-only) | I1–I8 | yes |
| **fixture-integration** (committed mini-xlsx → real pipeline in tmp dir) | M8, M9(CLI: exit 1, stderr, no traceback), M12, M14–M16, F1, F2, F3, F5, P1 | yes |
| **real-data gate** (local only, never in suite) | Scenario A incl. golden iGavel check | no — required before "ship" |
| **manual/human** | S2 eyeball, spot-trace, real-user read | no — reserved deliberately |

Fixture strategy (ratified J3): the suite runs entirely on synthetic data — a committed ~20-row
DOL-shaped xlsx in `tests/fixtures/` plus in-memory frames — so a fresh clone tests everything
without a 100 MB download. Real data is the acceptance gate's job, not the suite's.

## 7. Acceptance scenarios — the ship gate (ratified)

**Scenario A — the golden run** (on the JP-locale Windows machine dec. #14 exists for):
1. Real `LCA_Disclosure_Data_FY2025_Q4.xlsx` in `data/raw/`, no `output/private/` state →
   `python scripts/run.py`.
2. Observe: conversion runs or skips cleanly · all four `[verify]` lines print, golden =
   **iGavel, 7 filings, PASS** · three artifacts exist · report shows the **full** table, all 5
   caveats, single-quarter note, visible gap-read placeholder · blank `hiring_now.csv` created ·
   exit 0 · zero stack traces · no mojibake.
3. Hand-fill one `hiring_now` row; save a real `gap_read_filled.md` → re-run → both render;
   the hand-filled CSV is byte-identical where the tool is concerned.

**Scenario B — the failure face:** fresh clone, empty `data/raw/` → `run.py` exits 1 with the
plain-English no-data message. No traceback.

**Human pass (no assertion replaces it):**
- **Spot-trace:** pick 2 shortlist employers, filter the raw xlsx by hand, confirm filing counts
  match — "every number traces" verified by a person, repeated for every new quarter.
- **Real-user read:** the applicant (design §1's single validation user) reads the report and can
  act on it — names the 3 projects back, understands the caveats.

A + B green **and** the human pass done = trusted to ship. Nothing less.

## 8. Trust check — is the green light real

Scoped to the load-bearing items (ratified J2):

1. **The verify layer must demonstrably fire (V1–V4, MUST):** each of the four checks gets a
   negative test — `check_nonempty` on an empty selection, `check_filing_count_sum` on a table
   with a dropped and a duplicated filing, `check_employer_collapse` on stats where groups > raw,
   `check_golden_top_employer` on an FY2025Q4 frame where iGavel is not top — each must raise
   `RunwayError`. A check that can't fail manufactures confidence on every run.
2. **The ⚠ items are the suite's own proof:** every known-failing test must actually fail against
   today's code before its fix lands. A ⚠ test that passes untouched means the test is wrong.
3. **Fresh-context assertion review (one-time):** after the suite is built, a different
   model/session reads the tests against this spec and flags tautologies — assertions that cannot
   fail, fixtures that never exercise the branch, mocks that assert the mock. Findings return to
   this document as amendments.

### 8.3 Assertion review — record (2026-07-04)

> Ran after the automated suite was built: a fresh-context reviewer (separate session, given the
> spec + code-under-test + tests, no memory of writing them) hunted tautologies, false xfails,
> fixtures that miss their branch, mocks that assert the mock, and traceability gaps —
> cross-checking with `pytest --runxfail`. **Verdict: trustworthy as the automated leg of the v0
> ship gate, no blockers.**

**Clean, with evidence:**
- **False xfails — none.** All nine ⚠ tests fail at their asserted line for the exact contracted
  mechanism (F1/I8 `2 == 1` double-count; F2×2 real `UnicodeDecodeError` traceback; F3 pyarrow
  traceback; F4 `pending is False`; F5 literal `nan` cell; F7 `DID NOT RAISE`; M13 live
  `onmouseover="`). `xfail_strict=true`, 0 xpassed — no ⚠ item passes untouched (§8.2 holds).
- **Tautologies — none.** M14 caveats and M16 provenance assert against independently-stated
  oracles (retyped caveat literals; the hand-derived `EXPECTED` dict re-verified row-by-row),
  not the code's own source.
- **Mocks / traceability — clean.** `monkeypatch` only redirects path constants; every
  must-index row maps to a named test; §6 methods match; no scope-creep tests.

**Findings reconciled into the suite:**

| # | Finding | Fix |
|---|---|---|
| 1 | M15's cp932 end-to-end test was **vacuous** — the success path prints no non-ASCII, so it stayed green even with `force_utf8` fully broken (proven by counterfactual). | Added a **unit** test of `force_utf8()` (reconfigures both stdio streams to UTF-8 `errors='replace'`, sets `PYTHONUTF8`); relabeled the end-to-end test as an environment smoke. M15 gains a unit leg (§6). |
| 2 | M14 asserted the median-wage cell only in its **null (—)** state; a median→min/max wiring swap would pass. | Added rendered-median assertions (`$68,500`, `$81,800`) that only match the median, pinning the wiring end-to-end. |
| 3 | F3's xfail `reason` over-claimed the convert-side "sticky-skip" path, which the test does not exercise. | Trimmed the reason to the read-path traceback it actually pins. |

**Findings logged, deliberately deferred (silence ≠ oversight):**
- **M14 wage-excluded note, absence branch** (0-excluded → note vanishes) is not exercised — no
  0-excluded fixture exists; low value, deferred. (The presence branch and the single-quarter
  note's absence branch *are* tested.)
- **F3 convert-side sticky-skip variant** (a truncated parquet newer than its xlsx, never rebuilt)
  is not exercised; the dangerous consequence — the read-path traceback — is covered by the F3
  xfail. Deferred with the F1/F2/F3 fix step.
- **Code observation (not a test defect):** `verify.check_employer_collapse` embeds its own
  spellings and reports "verified on synthetic names" — a mild self-reference at the *code* level.
  The V3 negative test still fires the real `groups > raw` branch. Logged for the design doc.

---

*Ratification record: baseline M1–M16 (all MUST); J3 synthetic+real-gate; J1 hypothesis dev-only;
J2 negative tests + assertion review; J5 MUST incl. breakout; J4 test-as-designed + log gap;
J7 no-crash-counted-as-is; skips S1/S2/S4/S5 accepted, S3→P1, S6→D1; ship gate as written;
sweep F1–F4 MUST, F5 SHOULD, F6 ratified base-match, F7 note. All decisions by the owner,
2026-07-02.*

---
---

# v1 — Data-pipeline slice

`test-spec slice · ratified 2026-07-06` — ownership record: `RATIFICATION_LOG_v1.md`, Sitting 2.

## v1.1 Orientation

**Under test (the slice):** the v1 automated data pipeline that replaces v0's manual
"download-and-drop" — [`scripts/fetch_quarters.py`](scripts/fetch_quarters.py) (discover +
download + prune DOL quarters), [`scripts/build_shortlists.py`](scripts/build_shortlists.py)
(per-title incremental shortlist build + manifest), the
[`data-pipeline.yml`](.github/workflows/data-pipeline.yml) CI workflow's gating, and the
**engine seams** they reuse (`discover_quarters`, `load_quarters`,
`supersede_cumulative_quarters`, `build_sponsor_table`, the `verify` layer).

**Design authority:** `docs/decision_log.md` **dec. #22** (scheduled fetch + HEAD-probe
discovery), **#23** (commit processed parquet), **#24** (per-title incremental shortlists),
grounded on **#21** (cumulative-FYTD supersession). There is no local v1 design doc; the
Notion Design Doc is the upstream copy. Items decided during *this* slice's dialogue carry
their ratify-call letter (A–K) and are marked **[ratified-in-test-spec]**; the design
amendments they owe are listed in §v1.6.

**Slice boundary (declared):** this slice covers the fetch/build scripts, the CI gating, and
the engine seams. **Out of slice, owed to the v1 sweep:** the GitHub Pages frontend that
reads `index.json`; the deferred absorption of the v0 private report into the site path
(dec. #24); the manifest's `generated_at_utc` churn (benign — only committed when something
else changed; documented, not tested). v0 engine internals are already covered by §1–§8 M1–M16
/ F1–F8 / I1–I8 — **re-affirmed at the seams, never duplicated.**

**Acceptance statement:** the v1 pipeline is trusted when Scenario D (synthetic incremental
proof) is green in the suite, the v0 suite (§P17) stays green, the extracted CI orchestrator's
gating unit-tests are green, **and** the first real scheduled/dispatched CI run (Scenario C)
downloads + converts + builds against live DOL and is a clean no-op on an already-current repo.

**Where the risk concentrates (ratified):**
1. **Committed-data destruction from a partial signal.** A single flaky HEAD probe (B) or a
   scoping flag (G) or a killed mid-write (H) can *delete or corrupt* parquet the frontend
   serves — and the pipeline commits the damage. This is the slice's dominant blast class.
2. **The repeat-sponsor signal's ≥2-fiscal-year floor.** The lookback window is exactly 2 FYs
   (dec. #22); anything that silently drops an FY collapses the product's core edge to false.
3. **Incrementality correctness.** "Already saved" must mean "matches current definition AND
   window" (C) or a config edit silently no-ops; and the build must be genuinely idempotent (P9)
   or CI commits churn.
4. **The multi-title loop vs. the verify trust contract (A).** One title must not take down the
   others (empty case) — but an integrity failure must still stop everything (engine-bug case).

### v1 must-test index

⚠ = **design-anchored and expected to fail against today's code** — author blind to the
implementation, commit red-first (dec. #20 xfail-strict pattern), drive to green.

| # | Behavior (one line) | Traces to | Anchor class | Method | Tier |
|---|---|---|---|---|---|
| P1 | `current_fiscal_year`: Sep 30 → FY N; Oct 1 → FY N+1 (Q1); total fn of injected date | dec.#22; `fetch_quarters.py:53` | design | unit | MUST |
| P2 | `discover_upstream`: per FY, newest-first probe → highest **published** quarter; records its URL | dec.#22; `:79` | design | unit (mock) | MUST |
| P3 | fetch reconcile: published-not-in-`have` → download; in-`have` → skip; `changed` iff disk changed | dec.#22; `:124` | design | integ (mock) | MUST |
| P4 | **Conservative prune:** prune ONLY for supersession (newer same-FY seen) or out-of-window; never on a probe-miss incl. 404/5xx/429 while another FY resolves | dec.#22; **B [ratified-in-test-spec]**; `:161` | design | integ (mock) | MUST ⚠ |
| P5 | Total blackout (no FY published) → `RunwayError` naming the README URL template; **prunes nothing** | dec.#22/#23; `:138` | design | unit | MUST |
| P6 | Network `URLError` → `RunwayError`, plain English, names the URL/README (self-diagnosing) | dec.#15; `:71,112` | design | unit | MUST |
| P7 | fetch & build emit `changed` to `$GITHUB_OUTPUT` = true iff disk changed | dec.#22/#24; `:172` | design | unit | MUST |
| P8 | build triggers: no-op when current · new quarter → all rebuild · new title → only it · removed title (from **full** ROLE_SOC) → pruned | dec.#24; `:78` | design | integ | MUST |
| P9 | build **idempotence**: 2nd run on unchanged inputs writes no parquet, `changed=False` | dec.#24; `:103` | design | property/integ | MUST |
| P10 | manifest consistent + frontend-readable: `window`, per-title `soc_codes`/counts/parquet name = what was built | dec.#24; `:126` | design | integ | MUST |
| P11 | fetch/engine agree: post-fetch `data/processed` = one parquet per in-window FY → `supersede` map empty | dec.#22 ↔ #21 | design | integ | MUST |
| P12 | Empty-result title → isolated, marked `empty` in manifest, others still build; **integrity-check** `RunwayError` → aborts whole run | dec.#24 fork; **A [ratified-in-test-spec]**; `verify.py`; `sponsors.py:227` | design | integ | MUST ⚠ |
| P13 | Saved-state key includes `soc_codes`+`wage_level`: editing a title's SOC (no new quarter) rebuilds it | dec.#24 amended; **C [ratified-in-test-spec]**; `:103` | design | integ | MUST ⚠ |
| P14 | CI gating decisions (convert-if-fetch-changed · commit-if-either · push retry) live in a testable `scripts/run_pipeline.py` orchestrator | dec.#22/#24; **E [ratified-in-test-spec]** | design | unit (orchestrator) | MUST ⚠ |
| P15 | `--titles` scopes the **build only**; prune always considers full ROLE_SOC; a scoped run never deletes an out-of-subset title | dec.#24; **G [ratified-in-test-spec]**; `:92,119` | design | integ | MUST ⚠ |
| P16 | Shortlist parquet written atomically (`.part`→replace); `up_to_date` verifies **readability**; retry-after-crash self-heals | F3 precedent; **H [ratified-in-test-spec]**; `:62,103` | design | integ | MUST ⚠ |
| P17 | v0 regression: the existing suite stays green (v0 private path untouched, dec.#24 additive) | dec.#24; v0 §1–§8 | code (pin) | suite | MUST |
| P18 | Download truncation guard: `Content-Length` mismatch → `RunwayError` + **no file at `dest`** | dec.#7; **D [ratified-in-test-spec]**; `:115` | design | unit (mock) | SHOULD (green — guard already built; see §v1.7 amendment + dec. #31) |
| P19 | `git push` non-fast-forward → rebase-or-retry contract; a run's regenerated data is not silently discarded | dec.#22; **K [ratified-in-test-spec]**; `yml:66` | design | orchestrator unit + review | SHOULD |
| P20 | `discover_quarters`: two files with a case-only difference mapping to one FY label → deterministic tie-break or hard error, never a silent drop | **J [ratified-in-test-spec]**; `sponsors.py:101` | code (pin) | unit | SHOULD |
| P21 | `quarters_superseded` manifest field reports a **real** same-FY collapse (capture the map, don't discard it) | dec.#16; **I [ratified-in-test-spec]**; `:88,73` | design | integ | SHOULD |

## v1.2 What "correct" means — the load-bearing rows

- **P4 (B)** The prune loop must never treat "this in-window FY didn't answer my probe this run"
  as "delete it." DOL serves stable permanent links and never un-publishes a quarter, so a
  missing probe is *always* a transient failure or a template change. Concretely: given committed
  `{FY2025Q4, FY2026Q1}` and a run where the FY2025Q4 HEAD returns 503/429/404 while FY2026Q1
  returns 200, FY2025Q4's parquet **survives**. `check_nonempty`… — the test matrix must include a
  5xx/429, not just a 404, and the case where *another* FY resolves (so the total-blackout guard
  P5 does not fire). Blast: the ≥2-FY repeat-sponsor floor collapses; the site self-heals only on
  a later successful probe.
- **P12 (A)** Two failure kinds diverge. An **empty-result** title (`No certified rows matched…`)
  is a normal outcome for a thin niche role → skip it, record `status: empty` in its manifest
  entry, keep building every other title. An **integrity-check** failure
  (`check_filing_count_sum`, `check_employer_collapse`) means the engine is miscounting — which
  corrupts *every* title in the run — so it still raises and aborts the whole build; nothing ships.
  Isolating an integrity failure would ship corrupted siblings while the check that says "do not
  trust this run" is filed as "one title skipped." *Today the code raises on both and aborts on
  both — P12 is red on the empty-isolation half.*
- **P13 (C)** `up_to_date` today compares only the window. The manifest already stores `soc_codes`;
  the key must become (title × definition × window) so that editing `ROLE_SOC["design"]` without a
  new quarter marks the title not-saved and rebuilds it. *Red today.*
- **P15 (G)** `build_all(only_titles=…)` currently restricts `titles`, then the stale-prune loop
  (`set(prior) − set(titles)`) deletes every title *not in the subset* and the manifest is
  rewritten with only the subset — so `--titles design` silently deletes `engineering`'s parquet
  and manifest entry. A scoping flag must never remove. *Red today.*
- **P16 (H)** `to_parquet` writes directly (no `.part`), and `up_to_date` checks only that the file
  *exists*. A process killed mid-write leaves a truncated parquet; because the prior manifest entry
  still matches the window, the next run skips the rebuild and **serves the corrupt file forever**.
  Mirror F3: atomic `.part`→replace on write, and `up_to_date` must confirm the parquet actually
  reads. This also makes retry-after-crash self-healing. *Red today.*

## v1.3 Invariants — property-test candidates

| # | Property (falsifiable statement) | Anchors |
|---|---|---|
| Q1 | `current_fiscal_year` is total and monotone across the Oct 1 boundary; same date → same FY | P1 |
| Q2 | `build_all` is idempotent: a second run on unchanged inputs writes no parquet and reports `changed=False` | P9 |
| Q3 | **Prune safety:** a committed in-window FY parquet is removed ONLY if a newer same-FY quarter was positively observed, OR the FY is out of the lookback window | P4/B |
| Q4 | fetch/engine agreement: after a completed fetch, `supersede_cumulative_quarters(discover_quarters(processed))` returns an empty superseded map | P11 |
| Q5 | `--titles` never shrinks the manifest's title set relative to `ROLE_SOC ∩ prior-manifest` | P15/G |

## v1.4 Failure modes & edge cases — triaged

| Case | L / B / C | Tier | Where |
|---|---|---|---|
| Transient single-FY probe failure (404/5xx/429) prunes committed data | **med** / **high** (kills repeat-sponsor) / low | MUST ⚠ | P4/B |
| `--titles <subset>` deletes out-of-subset titles | med (any scoped local run) / high / low | MUST ⚠ | P15/G |
| Killed mid-write → truncated shortlist served forever (no self-heal) | med (CI OOM/timeout) / high / low | MUST ⚠ | P16/H |
| Empty-result title aborts the whole multi-title build | high once title #2 lands / med / low | MUST ⚠ | P12/A |
| SOC edit without a new quarter silently no-ops | med / med / low | MUST ⚠ | P13/C |
| Total upstream blackout wipes all parquet | low / high / low | MUST | P5 (guard exists) |
| `git push` non-fast-forward discards a run | low-med / med (a week to next run) / low | SHOULD | P19/K |
| `discover_quarters` case-only label collision drops a file | low / med / low | SHOULD | P20/J |
| `quarters_superseded` can't report a real collapse | low / low / low | SHOULD | P21/I |

### The SKIP list (ratified — considered and deliberately not tested, because…)

| Skip | Reason |
|---|---|
| SK-v1-1 Live DOL network I/O in the suite | **F:** suite mocks the network; the real fetch is proven by the first scheduled CI run (Scenario C). DOL changes ~4×/yr and a break gives ample response time; the control is **diagnosability** (P5/P6 name the URL template), not a suite test. VCR/live-smoke rejected (staleness / re-introduced flakiness). |
| SK-v1-2 Real 80–140 MB stream perf/memory | Inherits v0 S1; observed incidentally in Scenario C. |
| SK-v1-3 kill-mid-stream **download** atomicity (vs the Content-Length guard) | Trusted to the atomic-rename idiom + F3 downstream + P18; only the mockable truncation guard is asserted. |
| SK-v1-4 `concurrency`-group internals + `[skip ci]` loop-avoidance | GH-Actions primitives, review-only per **E**; the dangerous consequence (push race) is promoted to P19/K. |

## v1.5 Verification plan — method per item

| Method | Items | Automated? |
|---|---|---|
| **unit** (pytest) | P1, P5, P6, P7, P14, P18, P20, Q1 | yes |
| **integration** (mocked network; fake `data/processed`/manifest in tmp dir) | P3, P4, P8, P9, P10, P11, P12, P13, P15, P16, P21, P19 (orchestrator contract) | yes |
| **property** (hypothesis, dev-only) | Q1–Q5 | yes |
| **suite-regression** | P17 (the v0 suite, unchanged) | yes |
| **manual / review** | P14 YAML residue + P19 push (code review); **Scenario C** = the real-fetch acceptance leg | no |

**Authorship contract (carried downstream).** The design-anchored ⚠ items — **P4, P12, P13,
P14, P15, P16** — must be authored by a test-writer **blind to the implementation**: a fresh
session given `docs/decision_log.md` dec. #22/#23/#24 + this v1 slice section only, never the
scripts or the diff. Commit them **red-first** (xfail-strict, dec. #20 pattern) and drive to
green in the build step. **P17** (v0 suite) and **P20** (label-collision pin) are regression pins
that may read the code. Network is mocked throughout (SK-v1-1).

## v1.6 Acceptance scenarios — the slice ship gate

- **Scenario C — real fetch (the reserved real-data leg).** The first scheduled or
  `workflow_dispatch` CI run against live DOL: the URL template resolves, the current-FY quarter
  downloads + converts, per-title shortlists build, and — on an already-current repo — the run is
  a clean **no-op** (fetch `changed=false` → convert skipped → commit skipped). Observed once,
  logged. This is the v1 analogue of v0 Scenario A.
- **Scenario D — incremental proof (synthetic, in-suite).** Seed a tmp `data/processed` with
  FY(n−1)+FY(n) parquet, then: run `build_shortlists` twice → first builds, second is a no-op
  (`changed=False`, no parquet rewritten); add a title → only it builds; advance the window
  (drop-in a new-FY parquet) → all titles rebuild; remove a title from `ROLE_SOC` → its parquet is
  pruned. Plus the prune-safety and `--titles` scoping cases (P4, P15) driven with a fake prober.

**Gate:** Scenario D green in the suite **and** P17 (v0 suite) green **and** the P14 orchestrator
unit-tests green **and** Scenario C observed once = the slice is trusted. A green suite alone is
not the gate — Scenario C proves the live source, which the suite deliberately never touches.

## v1.7 Trust check — is the green light real

- **The ⚠ items are the slice's own proof.** P4, P12, P13, P14, P15, P16 must each fail
  against today's code before their fix lands (xfail-strict, 0 xpassed) — a ⚠ that passes untouched
  means the test is wrong. Because they're authored blind to the implementation, the builder's
  blind spot and the test author's blind spot are not the same blind spot.
- **Fresh-context assertion review (one-time), after the suite is built:** a different
  model/session reads the v1 tests against this section and hunts tautologies — a mocked prober
  that never exercises the prune branch, an `up_to_date` test that asserts the mock, a manifest
  oracle copied from the code rather than independently stated. Findings return here as amendments,
  as in v0 §8.3.

**Spec amendment (2026-07-06, Test-Build reconciliation — mirrors v0 §8.3).** P18 was marked ⚠
but is **already green**: the Content-Length truncation guard exists at `scripts/fetch_quarters.py:115`
(stream to `.part` → compare bytes vs `Content-Length` → unlink + `RunwayError`, so `dest` is never
created), ratification call D reads "test existing behavior," and the ratified red-first set is
{A,B,C,E,G,H} = {P12,P4,P13,P14,P15,P16} — which never included D/P18. P18's ⚠ marker is struck in
§v1.1/§v1.5/§v1.7; its test stays a plain green pin (never xfail). Logged as `docs/decision_log.md` dec. #31.

## v1.8 Design amendments owed (recorded so silence ≠ oversight)

Route to `docs/decision_log.md` (the *why*, in-repo) and the Notion v1 Design Doc §5/§6
(pipeline shape). **This skill wrote only this spec + `RATIFICATION_LOG_v1.md`.**

1. **dec. #24 open fork CLOSED (A):** zero-result title → isolate + mark `empty`; integrity-check
   failure aborts the whole run.
2. **dec. #24 saved-state key (C):** (title × window) → (title × **definition** × window).
3. **dec. #22 prune rule (B):** explicit — supersession or out-of-window only; never on a
   probe-miss (incl. 5xx/429 while another FY resolves).
4. **CI architecture (E):** gating consolidates into a testable `scripts/run_pipeline.py`;
   YAML shrinks to checkout → orchestrator → push.
5. **`--titles` semantics (G):** scope-only; never prunes out-of-subset titles.
6. **Shortlist output write (H):** atomic + readability-checked, at F3 parity.

*Ratification record (v1 slice): calls A–K all ratified by the owner 2026-07-06 via
prediction-before-reveal; 10/11 predicted · 1 surprised (A) · 0 no-opinion; two owner-overrides
(E extraction, F diagnosability) and two owner-expansions (I, J fixed over noted). MUST ⚠ set =
P4/P12/P13/P14/P15/P16 (design-anchored, red-first); SHOULD = P18/P19/P20/P21; SKIPs
SK-v1-1..4 accepted. Full per-call record: `RATIFICATION_LOG_v1.md`, Sitting 2.*
