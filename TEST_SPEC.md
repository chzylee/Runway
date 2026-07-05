# Runway v0 — Test Spec

`test-spec v0.1.1 · 2026-07-02, amended 2026-07-04` — **ratified 2026-07-02** through
item-by-item dialogue; **amended 2026-07-04** to reconcile the §8.3 fresh-context assertion
review after the automated suite was built (see §8.3).
Living document: amend as the design evolves; do not clobber. The diff history is the record
of what changed about what-must-be-true.

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
