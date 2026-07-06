# Build status — Runway

Where this project sits in the Ship Pipeline, and what finishes the build. One
page so anyone — not just the author — can pick up Runway cold and know the next
move. The generic pipeline definition lives in the Ship Pipeline wiki; this file
is Runway's *position* in it, kept current in the repo where a stranger can read
it without Notion access.

## v1 — current position

v0 is shipped and owned (history below). **v1 (the UX + value-clarity pass) is
in the Design stage:** scope was ratified 2026-07-05 (`RATIFICATION_LOG_v1.md`,
this repo) and engineered into a Design Doc + Build Prompt. Both deliverables —
along with the `v1 Build` pipeline index — live in **Notion**, not this repo:
[v1 Build](https://app.notion.com/p/39476356d6fe81568c4dea6bf8a01e05)
(→ [Design Doc](https://app.notion.com/p/39476356d6fe81cda2d9fdf7f78c0dc2),
[Build Prompt](https://app.notion.com/p/39476356d6fe8101a594ed82d20f6f5f)).
Scope authority: [v1 — Direction & Scope](https://app.notion.com/p/39476356d6fe81719a01c5eefd0e1277).
Next stage: Pre-Test Build (reconcile code against the Design Doc) — not started.

### v1 data-pipeline slice — Test Build + finish-build complete

The automated data pipeline (`scripts/fetch_quarters.py`, `scripts/build_shortlists.py`,
`scripts/run_pipeline.py`, the `data-pipeline.yml` CI, and the engine seams they reuse) has run
its own spec→build→finish loop, additive to the v0 private path:

| Stage | Produces | Status |
|---|---|---|
| Test Spec (slice) | `TEST_SPEC.md` §"v1 — Data-pipeline slice" | ✅ ratified 2026-07-06 (`RATIFICATION_LOG_v1.md`, Sitting 2) |
| Test Build | `tests/test_v1_*.py` + `tests/v1_support.py` | ✅ 13 ⚠ committed red-first (xfail-strict, 0 xpassed) |
| finish-build | the 6 MUST behaviors (dec. #25–#30) | ✅ driven to green 2026-07-06 (Sitting 3) |

**Verify:**

```
pip install -r requirements.txt -r requirements-dev.txt
pytest            # expect: 124 passed, 3 xfailed
```

The **3 xfailed** are SHOULD items deliberately deferred to v1.1 (dec. #32), markers kept, not
dropped: **P20** (case-only label collision — CI-only, open tie-break-vs-hard-error fork, touches
v0 engine), **P21** (`quarters_superseded` surfacing — provenance only, invariant already guarded),
**P19** (push rebase-or-retry — concurrency-serialized, no data loss). v0's suite (95) is untouched
(P17). **Out of slice, owed to the v1 sweep:** the GitHub Pages frontend, the v0-report absorption
(dec. #24), and the Notion Design Doc §5/§6 cumulative-FYTD update. Scenario C (the first real
scheduled/dispatched CI run against live DOL) is the reserved real-data acceptance leg.

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
