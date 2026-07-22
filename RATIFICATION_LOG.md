# Ratification log — Runway v0

The demonstrated-ownership record for the build. Each entry is a decision or a
finish-build item worked through **prediction before reveal**: the owner stated
the fix / location / trap *before* the seam analysis was shown, and the delta
was logged. Outcomes: `predicted` (fast earned yes) · `surprised` (had an
expectation the reveal contradicted) · `no-opinion` (couldn't form one — a
finding, not a failure). Surprises carry a reading pointer forward to
own-your-code.

Companion to `docs/decision_log.md` (the *why* of each fork) and
`docs/build_status.md` (the *position*). See also TEST_SPEC §8 (the trust check).

---

## Stage 6 — WARN code-fix (the 9 ratified-but-deferred behaviors)

Entry state: **86 passed, 9 xfailed**. Worked cheapest-first; F1/I8 carries a
design fork escalated to full ratification.

### Item 1 — M13 href-attribute breakout · **diagnosis predicted, mechanism surprised**

- **Owner's prediction:** the renderer never looks for the `"`, so `onmouseover`
  slips through the `_LINK` regex (`[^)\s]+` swallows the quote) and through the
  `.sub()` into the href. A `"` doesn't belong there and must be recognized;
  instinct was to *strip* the content between the quotes. Named trap: "a careless
  escape or guard that might cut off more than it should."
- **Reveal:** diagnosis was exact — both the regex and the sub. The **ratified
  mechanism is escape, not strip** (TEST_SPEC M13 §2): line 99
  `html.escape(raw_line.strip(), quote=False)` → `quote=True`, so the `"` becomes
  `&quot;` *before* `_LINK` captures the URL. The href is inert but the URL text
  is **preserved** — matching the established renderer contract (the `javascript:`
  test asserts the bad URL survives as text; hostile input is rendered inert,
  never deleted). The owner's own named trap — "cut off more than it should" — is
  precisely why strip loses to escape.
- **Sharpening (mine):** the escape-side trap is re-escaping only the captured
  URL, which double-escapes ampersands (`&amp;` → `&amp;amp;`) and mangles
  `?a=1&b=2`. `quote=True` at the single escape point escapes the line exactly once.
- **Reading pointer:** `test_M13_javascript_url_not_linkified` — the design
  precedent for *inert, not deleted*.
- **Fix:** `scripts/build_report.py:99` (`quote=True`); marker removed at
  `tests/test_report_unit.py`. Red→green: 86p/9x → 87p/8x, no regression.

### Item 2 — F4 empty/whitespace gap read · **predicted (+ owner enhancement)**

- **Owner's prediction:** `read_text` reads the whitespace and nothing checks
  content before returning; add a check for content after trim. Trap named was
  not a naive-fix failure but a **UX hole the test doesn't force**: a user who
  saved a blank file should get a signal it was ignored, not the same silent
  placeholder as an absent file — so *also log that only whitespace was found*.
- **Reveal:** diagnosis + mechanism were the ratified fix exactly
  (`if raw.strip(): render else fall through`). The owner's log instinct was
  adopted into the build (the bare test — `assert pending is True` — would pass a
  silent fall-through; the owner improved on the contract).
- **Sharpening (mine):** (1) line 130's read is the exact seam item 5 (F2-md)
  wraps for cp932 — reading into `raw` on its own line sets that up for free;
  (2) scope line held at *empty/whitespace* (`.strip()`); "renders-empty markdown"
  is not owed.
- **Fix:** `scripts/build_report.py:_gap_read_section` (content check + owner's
  whitespace-present log); marker removed. Red→green: 87p/8x → 88p/7x, no regression.

### Item 3 — F5 blank CSV cell → "nan" · **no-opinion (mechanism) + predicted trap**

- **Owner's prediction:** ruled out output-munging with a sharp trap — a naive
  string-strip of "nan" over-matches and corrupts legit text (**Financial →
  Fiicial**); the fix must be at the **read**, recognizing a blank-cell-became-NaN.
  Declared **no-opinion honestly** on the specific read-side mechanism.
- **Reveal:** mechanism was already in-file 20 lines up (hiring-now read, line 56):
  `pd.read_csv(..., dtype=str).fillna("")`. The **deeper trap the no-opinion
  surfaced:** `dtype=str` reads the *whole* frame as strings incl. the wage column,
  and `_money()`'s `f"${value:,.0f}"` raises `ValueError` on a string — so
  `dtype=str` **alone crashes M14** (`$68,500`/`$81,800`). Ratified fix is two
  halves: read as str, then `pd.to_numeric(..., errors="coerce")` the wage columns
  back — and `coerce` gives blank-wage → NaN → em dash for free.
- **Reading pointer (learning item):** `_money` at `build_report.py:143` — trace
  string vs NaN to own why the coercion is mandatory, not optional.
- **Fix:** `scripts/build_report.py:_read_inputs` (dtype=str + wage re-coercion);
  marker removed. Verified F5 **and** M14 green together. Red→green: 88p/7x →
  89p/6x, no regression.

### Item 4 — F7 mixed-generation guard · **diagnosis predicted; mechanism over-scoped**

- **Owner's prediction:** the CSV and provenance are "internally-trusted" to
  correspond and nothing enforces it — the explicit link is missing. Avoided a
  real trap (mtime/"when the file was made" is fragile). Proposed mechanism: a
  **timestamped-filename-pairing** scheme (`sponsors_<timestamp>_*`).
- **Reveal:** diagnosis exact; trap-avoidance sharp. The ratified fix (note-tier)
  is the cheap **content assertion** `len(table) == provenance["employer_groups"]`
  — the pair already carries a consistency token. The owner's filename-pairing is
  a *stronger* guarantee but wrong scope here: it would require rewriting the
  ratified test (forbidden) and blooms a note-tier guard into an artifact-naming
  redesign (build_shortlist/build_report/run.py/README/.gitignore).
- **DESIGN OBSERVATION (captured, deferred — silence ≠ oversight):** the count
  guard catches count-drift but not two runs that coincidentally produce the same
  employer count with different data. A structural link (shared generation token /
  timestamped artifact pair) would be strictly stronger. Route to the design doc's
  next revision as a candidate amendment; **not** built in v0 (beyond note-tier).
- **Fix:** `scripts/build_report.py:_read_inputs` (`groups != len(table)` →
  RunwayError, `.get` so a malformed provenance still fails plain-English not
  KeyError); marker removed. Red→green: 89p/6x → 90p/5x, no regression.

### Item 5 — F2 cp932 manual input (md + csv) · **no-opinion (mechanics) + predicted contract**

- **Owner's prediction:** goal is graceful cross-locale handling; a byte-level
  problem invisible at human-readable level; the caught error must **elucidate the
  encoding** so the user can act. No-opinion on the Python mechanics, honestly.
  (Also raised a cosmetic: `sponsors_levelI` `lI` legibility — see observation.)
- **Reveal:** contract instinct = dec. #15 exactly. Mechanics: utf-8 decode of
  cp932 bytes raises `UnicodeDecodeError`, which is not `RunwayError`, so
  `run_cli` doesn't catch it → traceback. Fix: catch `UnicodeDecodeError` at both
  manual-input reads and re-raise as RunwayError naming the file + fix (we *fail*,
  never `errors='replace'` silently). Traps: (1) **two sites, one parametrized
  decorator** — miss one and it's half-red; (2) scope only the two manual files,
  never the tool-written UTF-8 artifacts.
- **Reading pointer:** `run_cli` (`_util.py:42-56`) — which exception types it
  catches, and why a bare `UnicodeDecodeError` escapes.
- **DESIGN OBSERVATION (captured):** rename `sponsors_levelI.*` → hyphenated /
  disambiguated form (`lI` collides in most fonts). Cross-cutting, tied to no
  failing test; offered as a separate tidy pass after stage 6 green. Same thread
  as item 4's filename observation.
- **Fix:** `scripts/build_report.py` — `_stop_if_not_utf8` helper + try/except at
  `_load_or_create_hiring_now` (line 56) and `_gap_read_section` (line 130);
  marker removed. Red→green: 90p/5x → 92p/3x (parametrized ×2), no regression.

### Item 6 — F3 unreadable/truncated parquet · **predicted (mechanism)**

- **Owner's prediction:** an interrupted/uncontrolled write damages the engine's
  trusted deterministic input; fix is try/except around the parquet read, catch
  the natural pyarrow error, bubble up a descriptive RunwayError. (Transferred the
  F2 pattern independently.) Also raised auto-reencoding as a future UX direction.
- **Reveal:** mechanism was right. Sharpenings: (1) **scope the `try` to the read
  line alone** — `except Exception` is house-idiom (`convert_quarters.py:29`) but
  broad; a one-line try keeps it from masking a computation bug, which in the pure
  engine would be the dec. #15 anti-goal; (2) the message must say **`--force-convert`**,
  not "re-run" — the corrupt parquet is newer than its xlsx, so a plain re-run hits
  the mtime skip and loops on the same error (dec. #7). Confirmed `run.py` forwards
  the flag before instructing it.
- **DESIGN OBSERVATION (captured):** auto-reencoding for non-UTF-8 manual inputs
  (F2) — attractive for non-technical users but requires *guessing* the source
  encoding (cp932/shift-jis/latin-1 ambiguous), whose wrong guess silently
  corrupts. Fold into the owner's UX-updates thread; v0 fails safe by ratified call.
- **Fix:** `engine/sponsors.py:load_quarters` (tight try/except → RunwayError naming
  `--force-convert`); marker removed. Red→green: 92p/3x → 93p/2x, no regression.

### Item 7 — F1 + I8 cumulative same-FY overlap (THE FORK) · **surprised → full ratify → dec. #21**

Ran the full ratification protocol (not an execution item). Domain fact: DOL files
are cumulative FYTD, so a same-FY quarter re-lists earlier filings → double-count +
fabricated repeat_sponsor (MUST-tier).

- **Owner's prediction:** mechanism **B (supersede)** — collapse to one file, "should
  withstand existing tests." ID instinct: `CASE_NUMBER`. repeat = distinct quarters
  with a genuinely different filing.
- **Reveal 1 — surprised:** supersede breaks `test_M14_...two_quarters` (its Q2 isn't
  truly cumulative). Owner's *direction* was the more domain-truthful model, but the
  "zero blast radius" claim flipped. `CASE_NUMBER` is a **decoy column, not kept** —
  which cut *for* supersede (it needs no filing ID) and *against* dedupe.
- **Re-ratification (owner-critical honesty):** implementing surfaced a **second**
  broken test — **M6** — that I'd under-priced when the owner first approved ("amend
  M14" → actually "amend M6 + M14"). Went back with the real cost + the deeper finding:
  cumulative files make within-FY quarter repeat **unmeasurable** (no `DECISION_DATE`),
  so repeat is honestly a *fiscal-year* signal. Owner re-confirmed B with full cost:
  *"fully hold with this — it matches sustainable stable design."*
- **Mechanism built:** `supersede_cumulative_quarters` (latest file per FY; different
  FYs always kept); superseded quarters announced on console + in provenance
  (`quarters_superseded`, dec. #16 "nothing disappears silently"). repeat semantics →
  distinct fiscal years (dec. #10 amended).
- **Decision logged:** dec. #21 (supersede over refuse/dedupe, with why). dec. #10 &
  #11 amended inline. TEST_SPEC §5.1 F1 amendment **struck**. M6 + M14 fixtures amended
  to cross-FY and logged (deliberate correction of a misconception-encoding fixture,
  not an edit-to-pass).
- **Reading pointer:** `supersede_cumulative_quarters` + dec. #21 — trace why within-FY
  quarter repeat is unrecoverable from cumulative files; that's the load-bearing insight.
- Red→green: 93p/2x → **95 passed, 0 xfailed**, no regression.

---

## Stage 6 close — Definition of Done

- ✅ Suite **95 passed / 0 xfailed** (from 86p/9x); **every deferred marker removed**.
- ✅ **No previously-passing test regressed** (M6/M14 deliberately amended + logged, not broken).
- ✅ The one fork logged as a decision (**dec. #21**); owed design amendment (F1) **struck**.
- ✅ `docs/build_status.md` advanced: stage 6 ✅ → stage 7 (own-your-code) current.
- ✅ Ownership record complete (this file).

**Ownership scorecard (per item):**
- M13 — diagnosis predicted, mechanism surprised (strip → escape)
- F4 — predicted, + owner-added log enhancement
- F5 — no-opinion (mechanism) + predicted trap → learning item (`_money` / dtype)
- F7 — diagnosis predicted, mechanism over-scoped (captured as design observation)
- F2 — no-opinion (Python mechanics) + predicted contract → learning item (`run_cli`)
- F3 — predicted (mechanism)
- F1 — surprised → full ratify → dec. #21

Surprises & no-opinions carry the reading pointers above → own-your-code's study guide.

Handoff: the Acceptance Gate reads the failure faces as the user; own-your-code
inherits this surprise list.

---

## Sitting 2 (2026-07-22) — v1 reviewer prompt + output schema, treated as code

Artifact: `prompts/recommendations.md` (rewritten this session) and its embedded
JSON output contract, now carrying the **Inbound Appeal Career Coach** persona
(Persona Library v0.1.0). Rigor: standalone ratify over a 9-item decision list;
expanded to **11 judgment items** as threads surfaced new forks. Baseline:
`partial` — the design doc, decision log, Persona Library schema v1 and the
Cognitive Patterns Case Study *inform* this artifact but do not *specify* it.

**Protocol note.** Most of the listed decisions were made earlier in the same
session, so "predict what we decided" would have been theater. The prediction
surface was therefore moved to **how the written artifact behaves** — traces the
owner had not run. That preserved real information asymmetry and is what surfaced
items A1, B3, C1 and C2.

| # | item | expectation stated | pre-conf | outcome | origin | gap | decision | reading |
|---|---|---|---|---|---|---|---|---|
| A1 | Access check: unreadable vs absent materials | stop and ask; without materials the suggestions are empty | high | surprised | human+ai | missing-info | amend | — |
| A2 | Research disclosure when research can't run | all undoable research disclosed; never leave the user in the dark | high | predicted | human+ai | none | build | — |
| A3 | A "generic mode" that runs without materials | raised, judged low-value | high | predicted | human | none | demote | — |
| B1 | `distinctive_edge` presence + framing | shows, but unevidenced -> worth remembering, not confident enough to recommend | med | predicted | human+ai | none | build | — |
| B2 | `one_thing` mode under existing momentum | follow existing work without scrapping it; emphasise evidenced skills through it | med | predicted | human+ai | none | build | — |
| B3 | headline <-> one-thing coherence | (implied) one direction, not two | med | surprised | human | missing-info | amend | — |
| B4 | what "severe evidence-gap" means | owner authored the vehicle test | med | surprised | human | authored | amend | — |
| B5 | target- vs adjacent-evidenced | owner authored the scope distinction | med | surprised | human | authored | amend | — |
| B6 | report register (a coach going over it with you) | owner authored | med | surprised | human | authored | amend | — |
| C1 | role hardcoded in the prompt wrapper | nothing breaks if the title/SOC data is mapped correctly | med | predicted | human | none | amend | — |
| C2 | design-bound STEM-OPT caveat | same | med | predicted | human | none | amend (dropped) | — |

Mechanical, confirmed in one pass: **cap-at-3 selection**, **current-work input**.

**Accuracy over judgment items: 6/11 predicted, 5 surprised, 0 no-opinion.** Of the
five surprises, **three are `authored`** (owner-supplied additions, a positive gap)
and two are `missing-info`. **Zero `judgment` gaps -> this sitting assigns no
reading.**

### C1 / C2 — the finding that matters

Both were graded `judgment` on the first pass and **regraded to no-gap**: they are
**agent non-compliance**, not owner blind spots. The owner had stated across
multiple sessions that Runway is not design-restricted; the artifacts were built
design-bound anyway, and the protocol then tried to book that as his foresight
failure. Owning your own instruction being ignored is not foresight.

Root cause, evidenced rather than assumed:

- `docs/decision_log.md:411` — the engine is **already title-agnostic** (`build_sponsor_table` takes SOC codes, not a role name).
- `docs/decision_log.md:39` — design was a **v0 scope choice** ("keeps v0 scoped to design only").
- `README.md:3` and `web/index.html:13` nonetheless declared the product **"for international new-grad designers"**.

A temporary scope decision hardened into the product's identity in the prose
artifacts, and **no verifier bound the framing to the ledger**. Each new session
grounded in the README — the loudest "what is this" artifact — not in
`decision_log.md:411`. This is the Handshake Protocol's own named failure
(Runway's first run: a write-only decision log, correct in the ledger while the
code contradicted it) **recurring one layer up, in the prose**. See the Ship
Pipeline write-up: *Experiments and Review -> Design-doc drift in Runway v1*.

*Diagnosis refined after the sitting (per Noah, same day): the general pattern is
not "a scope decision hardened into an identity" (that describes only the audience
binding) but **implementation-time decisions not propagating back to the design
doc**. All eight drifts were recorded in the decision log or this file; capture
worked, propagation did not. The write-up above carries the corrected framing.*

Corrective, applied this sitting: caveat dropped at its single source
(`scripts/_util.py`), `{{ROLE_LABEL}}` token added, wrapper states the role is
**data, not a premise**, and `README.md` + the site tagline de-bound.

### Amendments applied

Access-check branch split (absent vs unreadable vs both-unreadable) · headline
binding restored on `how_it_signals` · vehicle/heading tie-break with the
can-the-skills-be-emphasised-through-it test · `evidence_scope` replacing the
`evidenced` boolean · `current_work_note` · report register · `{{ROLE_LABEL}}` ·
STEM-OPT caveat dropped (5 -> 4, count pins updated in two tests on purpose).

Verified: caveats parity OK (4) · 115 pytest passed · 17 vitest passed · all six
tokens fill end-to-end in the browser.
