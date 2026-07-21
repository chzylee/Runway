# Build status — Runway

Where this project sits in the Ship Pipeline, and what finishes the build. One
page so anyone — not just the author — can pick up Runway cold and know the next
move. The generic pipeline definition lives in the Ship Pipeline wiki; this file
is Runway's *position* in it, kept current in the repo where a stranger can read
it without Notion access.

## v1 — current position

### ▶ Resume here (2026-07-21, end of session)

**State: Increment 5 (automated fetch + CI) is BUILT and verified, pulled ahead of Increment 4 at
the owner's call (dec. #43). The data pipeline now discovers and downloads new DOL quarters on its
own. Next move is Increment 4 (paste + escape-render, the M13-successor security surface), then 6.**
Increments 1–3 + 5 are landed; only Increment 4 and the docs closeout (6) remain.

- **Increment 5 shipped (dec. #43):** `scripts/fetch_quarters.py` restored (HEAD-probe discovery of
  DOL's stable direct-link template, `.part`-temp truncation guard, conservative prune per dec. #27)
  + wired into `run.py` (fetch → convert → build; `--no-fetch` escape hatch) + `.github/workflows/
  data-pipeline.yml` (weekly `schedule:` + `workflow_dispatch`, fetch gated on `changed`, commits
  `web/data/` only on a new quarter, caches `data/processed/`). Partially reverses dec. #33 (re-adds
  cron + auto-discovery); the JSON-output / gitignored-parquet / untouched-engine parts of dec. #33
  all stand. Restored from git (`7198e0b^`), not rewritten; P20 case dropped (deferred v1.1, edits v0
  engine). **Verified 2026-07-21:** URL template resolves (FY2025Q3/Q4 + FY2026Q1 = 200, FY2026Q2 =
  404); real `discover_upstream` HEAD-probe vs live DOL returns `{FY2025Q4, FY2026Q1}` (golden window);
  suite 96 passed (14 fetch cases green). The real download + e2e run stays out of the suite (SK-v1-1).

**State (prior, 2026-07-17): the site spine (Increment 3) is BUILT and behaviorally verified.**
Increments 1–3 are landed: the data plane, the prompt template, and now the UI that connects them.

- **Increment 3 shipped:** `web/index.html` + `web/app.js` + `web/styles.css` — states
  Load → Shortlist → PromptReady with DataError+retry; pick Design → fetch `data/design.json` →
  caveats verbatim from the JSON + shortlist table (employer hyperlink [D8], repeat ✓, median
  wage — when null, dec. #37) + funnel line + provenance/CSV links → portfolio URL (validated,
  dec. #38) + optional pasted resume (in-memory only, visible stays-in-browser note) → checkbox
  select → fetch template, interpolate the 3 `{{TOKENS}}` (`{{SELECTED_ROWS}}` = design.csv-shaped
  CSV, dec. #36) → copy-box with Copy button (disabled/ready/copied; stale prompts auto-hide).
  All DOM writes are `textContent` — no `innerHTML` anywhere.
- **Build-discovered fork (dec. #35):** the Design Doc's serve root (`web/`, §13.3) couldn't reach
  its own template fetch path (`prompts/recommendations.md`, §5.4) — resolved by `run.py` mirroring
  the template to `web/prompts/recommendations.md` (committed build artifact, byte-identical,
  never hand-edited; D5 single source unchanged). **Owner should confirm-or-flip dec. #35.**
- **Verified (2026-07-17, headless-browser pass):** clean load → pick Design → 5 caveats verbatim,
  76 rows, honest funnel line, D8 links encoded; select 2 + portfolio → generated prompt has all
  tokens filled, iGavel CSV line identical to design.csv (RFC 4180 quoting); copy → "Copied ✓";
  input edits hide the stale prompt; simulated fetch failure → plain-English DataError, retry
  recovers. No console errors. JS tests + `/qa` leg stay deferred per the Build Plan.
- **▶ NEXT ACTION — Increment 4:** the paste-JSON → validate → escape-render step (§5.5, §6.2) —
  forgiving parse (strip ```json fences), tolerate missing fields with a soft note, ParseError
  state, and the non-negotiable T-JS-3 property: a hostile field value renders as inert text.
  Then **6** (docs closeout + owed bookkeeping). **5** (CI + automated fetch) is done — dec. #43.
- **To run/serve locally:** `python scripts/run.py` regenerates `web/data/` + the template mirror
  (needs a quarter's xlsx in `data/raw/` or its parquet in `data/processed/` — both gitignored,
  dec.#33); serve the site with `python -m http.server` rooted at `web/` (browsers block `fetch()`
  under `file://`, §13.3).
- **Authority:** Notion [Build Plan](https://app.notion.com/p/39576356d6fe8110bc1ac9232074760a)
  (6 increments) + [Design Doc](https://app.notion.com/p/39476356d6fe81cda2d9fdf7f78c0dc2); the
  pivot off the earlier scheduled-fetch/parquet slice is `docs/decision_log.md` **dec. #33**.
- **Watch-outs when you resume:** engine (`engine/`) + `convert_quarters.py` are UNCHANGED v0 — don't
  touch them; Runway never calls an LLM and never reads a user file (the resume is client-side prompt
  text only); the JS trio + `/qa` behavioral leg are the site's test stage, deferred per the Build Plan.

---

v0 is shipped and owned (history below). **v1 (the UX + value-clarity pass) is
in the Design stage:** scope was ratified 2026-07-05 (`RATIFICATION_LOG_v1.md`,
this repo) and engineered into a Design Doc + Build Prompt. Both deliverables —
along with the `v1 Build` pipeline index — live in **Notion**, not this repo:
[v1 Build](https://app.notion.com/p/39476356d6fe81568c4dea6bf8a01e05)
(→ [Design Doc](https://app.notion.com/p/39476356d6fe81cda2d9fdf7f78c0dc2),
[Build Prompt](https://app.notion.com/p/39476356d6fe8101a594ed82d20f6f5f)).
Scope authority: [v1 — Direction & Scope](https://app.notion.com/p/39476356d6fe81719a01c5eefd0e1277).
Next stage: Pre-Test Build (reconcile code against the Design Doc) — not started.

### v1 build — following the converged Build Plan (spine-first)

The v1 build follows the Notion [Build Plan](https://app.notion.com/p/39576356d6fe8110bc1ac9232074760a)
(6 increments, from the v1 Design Doc). An earlier scheduled-fetch / per-title-parquet-manifest
attempt was **superseded and deleted** — see `docs/decision_log.md` **dec. #33** (JSON output not
parquet, `workflow_dispatch` not cron; dec. #23 reverted). `TEST_SPEC.md` §"v1 slice" is marked
superseded.

| # | Increment | Status |
|---|---|---|
| 1 | Data emit + same-generation guard (`build_shortlist.py` → `web/data/{design.json, provenance.json, csv}`; `run.py` reshape; `build_report.py` deleted; `_util`→`web/data`) | ✅ built + verified 2026-07-06 |
| — | tests for Increment 1's emit (`tests/test_emit_unit.py`) | ✅ 12 green 2026-07-06 — closed §4.2 schema, null-wage→JSON null (F5), same-gen guard fires (F7); no reds |
| 2 | Recommendations prompt template + caveats parity (`prompts/recommendations.md`, `scripts/check_caveats_parity.py`) | ✅ built (`0e2fbe9`); parity passes |
| 3 | Site spine: fetch → shortlist → select → prompt-gen (`web/{index.html,app.js,styles.css}`; `run.py` template mirror) | ✅ built + browser-verified 2026-07-17 |
| 4 | Results render (escape-render, security-critical) | ◻ **next** |
| 5 | CI + deploy (`data-pipeline.yml`, schedule + workflow_dispatch; `fetch_quarters.py` restored) | ✅ built + verified 2026-07-21 (dec. #43; pulled ahead of #4) |
| 6 | Docs closeout + owed bookkeeping | ◻ not started |

**Increment 1 verify (local):**

```
python scripts/run.py            # with a quarter's parquet in data/processed/
# → writes web/data/design.json (+ .provenance.json, .csv); golden anchor fires;
#   observed: 76 employers / 95 filings over FY2025Q4+FY2026Q1, iGavel=7 pinned.
pytest                           # engine/pipeline + emit suite green (75)
```

The Python engine (`engine/`) and `convert_quarters.py` are **unchanged** from v0. The report path
and the deleted slice's tests are retired; the pipeline/emit test suite is authored fresh in the
next test-spec pass (JS trio + `/qa` leg defer to their stage per the Build Plan).

**Repo vs. Notion, for this project:** the repo holds code, the live position
(this file), the decision ledger (`docs/decision_log.md`), and ownership
records (`RATIFICATION_LOG*.md`) — things a stranger with repo access but no
Notion access still needs. Every pipeline-stage deliverable (Design Doc, Build
Prompt, Test Spec, Own-Your-Code, …) lives in the Notion project wiki
(`docs/notion.json` → `wiki_url`), per the Recording Standard. If a doc feels
like "what was decided and why for the code" it's repo; if it's "a pipeline
stage's deliverable artifact" it's Notion.

---

## v0 history

## Pipeline

| # | Stage | Produces | Status |
|---|---|---|---|
| 1 | Design Doc | design authority (Notion) | ✅ ratified |
| 2 | Build v0 | `engine/` + `scripts/` | ✅ done |
| 3 | Test Spec | `TEST_SPEC.md` | ✅ ratified 2026-07-02 |
| 4 | Acceptance Gate | human-verified ship gate | ✅ passed 2026-07-04 (dec. #19) |
| 5 | Test Build | automated suite (`tests/`) | ✅ complete 2026-07-04 |
| 6 | WARN code-fix | the 9 ratified-but-deferred behaviors | ✅ complete 2026-07-04 (dec. #21) |
| 7 | own-your-code | own-your-code onboarding (Notion) | ✅ generated 2026-07-04 (cross-model cold-read passed) |

## Where we are

**Stage 7 (own-your-code) is generated.** The engineering onboarding that confers ownership of the
build (cockpit + component map + each key decision on maint/UX/cost + data pipeline + drift + active
pass) lives on the **Notion v0 Build page as deliverable #6** —
`Own-Your-Code — Runway v0` (https://app.notion.com/p/39476356d6fe81e48972fbabb133aad4), alongside
the other ship-pipeline deliverables. It passed a different-lineage cross-model cold read (§8).
Disposable: regenerate it (re-run own-your-code, re-publish to Notion) after any code change. The
build is owned and ready.

---

### History

**Stage 7 (own-your-code) was reached from:** The Acceptance Gate (stage 4) passed on its
human legs — Scenario A (golden run), Scenario B (failure face), and the human
pass (spot-trace + real-user read), per dec. #19. The Test Build (stage 5)
produced the automated suite (86 passed, 9 xfailed), and **stage 6 (finish-build)
drove all 9 deferred behaviors to green through the predict→reveal ownership
loop** — suite now **95 passed, 0 xfailed** (verified 2026-07-04), every `xfail`
marker removed, no prior test regressed. The one design fork (F1 cumulative-quarter
overlap) was ratified as *supersede* and logged as dec. #21; its owed design
amendment (TEST_SPEC §5.1) is struck. The per-item ownership record is in
`RATIFICATION_LOG.md`.

The build is ready to hand off to own-your-code.

## Ship gate — the acceptance criteria

Defined once, in **TEST_SPEC §7** (not duplicated here): Scenario A + Scenario B
green on the target JP-locale Windows machine, **and** the human pass done.
TEST_SPEC §2 adds the automated leg — the suite green on synthetic fixtures — and
§8 is the trust-check that the green light is real (V1–V4 must fire; every ⚠ test
must fail before its fix lands).

## What "build complete" means (resolved 2026-07-04 — dec. #20)

v0 is complete — and ready for own-your-code — when the 9 deferred behaviors below
are **built**, each `xfail` marker removed as its behavior lands. `xfail_strict`
turns a now-passing test into a hard failure, so a fixed-but-not-unmarked item
fails the suite: the marker removal is enforced, not trusted.

Ship-with-deferred was the alternative; rejected because several of the 9 are
MUST-tier failure modes (see dec. #20).

## Stage 6 scope — the 9 owed behaviors (all built ✅)

Each was a committed failing test naming its spec anchor; each was driven to green
through the finish-build predict→reveal loop. Full per-item ownership record (what
was predicted / surprised / no-opinion, plus each trap) is in `RATIFICATION_LOG.md`.

| Test(s) | Owed behavior | Built |
|---|---|---|
| M13 href-breakout | escape the gap-read URL with `quote=True` at render | ✅ |
| F4 | empty/whitespace `gap_read_filled.md` → visible "pending review" placeholder (+ log) | ✅ |
| F5 | blank CSV cell renders blank, not `nan` (`dtype=str` + wage re-coercion) | ✅ |
| F7 | `build_report` asserts `len(table) == employer_groups` (same-generation pair) | ✅ |
| F2 (×2: csv, md) | cp932-saved manual input → `RunwayError` naming the file + fix | ✅ |
| F3 | unreadable/truncated parquet → `RunwayError` naming `--force-convert` | ✅ |
| F1 + I8 | cumulative same-FY overlap → **supersede** to latest file (dec. #21 fork) | ✅ |

## How to verify state yourself

```
pip install -r requirements.txt -r requirements-dev.txt
pytest            # expect: 95 passed, 0 xfailed
```

No 100 MB data download needed — the suite runs on a committed synthetic fixture
(TEST_SPEC §6). The real-data acceptance run (Scenario A) is the gate's job, not
the suite's.
