# Build status — Runway v0

Where this project sits in the Ship Pipeline, and what finishes the build. One
page so anyone — not just the author — can pick up Runway cold and know the next
move. The generic pipeline definition lives in the Ship Pipeline wiki; this file
is Runway's *position* in it, kept current in the repo where a stranger can read
it without Notion access.

## Pipeline

| # | Stage | Produces | Status |
|---|---|---|---|
| 1 | Design Doc | design authority (Notion) | ✅ ratified |
| 2 | Build v0 | `engine/` + `scripts/` | ✅ done |
| 3 | Test Spec | `TEST_SPEC.md` | ✅ ratified 2026-07-02 |
| 4 | Acceptance Gate | human-verified ship gate | ✅ passed 2026-07-04 (dec. #19) |
| 5 | Test Build | automated suite (`tests/`) | ✅ complete 2026-07-04 |
| 6 | WARN code-fix | the 9 ratified-but-deferred behaviors | ✅ complete 2026-07-04 (dec. #21) |
| 7 | **own-your-code** | `OWN_YOUR_CODE` onboarding | ⬅️ **current** |

## Where we are

**Stage 7 (own-your-code) is next.** The Acceptance Gate (stage 4) passed on its
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
