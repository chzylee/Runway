# Ratification log — Runway v1 (Direction & Scope)

The demonstrated-ownership record for the **v1 Direction & Scope** decision set
(Notion: `v1 — Direction & Scope`, 39476356d6fe81719a01c5eefd0e1277). Standalone
re-ratification of Noah's own trial-run notes via **prediction before reveal**:
for each item the owner stated the decision (or mechanism) *cold, in his own
words*, before the note's recommendation was shown, and the delta was logged.
Outcomes: `predicted` (fast earned yes — re-derived his own reasoning, often
sharper) · `surprised` (had/owned an expectation but did not reproduce it at the
stop) · `no-opinion` (couldn't form one — a finding). Because every item here
originated with Noah, this sitting measures **whether his hot-captured notes
survive a cold re-derivation** — not agreement with an AI's proposals.

Companion to `RATIFICATION_LOG.md` (the v0 build's finish-build record) and
`docs/decision_log.md` (the *why* of each fork). Read-only except this file; the
Notion v1 page was **not** edited (the Fable 5 wiki-tightening pass integrates
this — see Feed-forward).

---

## Sitting 1 — 2026-07-05 · full protocol (owner is the oracle: product direction + scope cuts)

**Decision contract.** Human function: Noah can assert, in product language,
*what v1 is, what it deliberately drops and why, what's committed vs. candidate
vs. captured-vision, and where Runway's value concentrates.* Evidence judged: a
direction claim + its concrete consequences (repo `decision_log` / Notion Design
Doc / the report itself), diffed against the expectation formed first. Pace:
threaded by risk area, scope-cuts first.

| # | item | expectation stated (owner, before reveal) | outcome | reading assigned |
|---|------|-------------------------------------------|---------|------------------|
| 1 | **Layer A** (automated postings signal) | Remove from scope — inherently unstable + not the most valuable direction; *was only ever an amenity, which is why it was out of v0.* | predicted | — |
| 2 | **Manual "hiring now?" column** | Cut it — a manual step is off-grain with the app's direction; an auto-added idea he never explicitly asked for. Refine the link-out as an **employer-name hyperlink** (removes a column instead of adding one). | predicted | — |
| 3 | **Rename "gap-read"** | Call it **"recommendations"** — the read *is* a set of recommendations; "gap" is internal vocabulary. (He'd failed his own term reading his own docs cold.) | predicted | — |
| 4 | **User-selectable target companies** *(net-new; not in the note)* | Yes, and **from the evidenced shortlist** (not free-text) — the user does the shortlist, then the read; the paste-prompt model lets them add more companies in their own LLM. | predicted | `docs/decision_log.md` #1 (LCA grounding — why free-text targets break the edge) |
| 5 | **Summary + overarching suggested action** (the eggs-in-one-basket fear) | Specificity induces anxiety; answer it with an **overarching recommendation** that ties the company-specific ones together / best-of-all-worlds, so a suggestion guides toward *a role*, not one company — via a domain thread that synergizes with the user's profile, or a pattern common across the involved roles/companies. | predicted (+ named the mechanism the note lacked) | — |
| 6 | **"Valuable skills to develop"** (the already-building user) | *Not reproduced cold* — forgot to restate it. Owns the idea (it's his), but did not surface it until prompted. | **surprised (recall)** | Source conversation + the **already-building user-state** that makes this a *separate* move from #5 (double-down-on-current-work ≠ start-something-new). Most-droppable item on a fast re-read — even by its author. |
| 7 | **Output visuals** | Headers that are real headers or at least newline-separated — "just clearly readable." Trimmed the note's "design-skills take a pass" to **optional**. | predicted (with a logged scope-trim) | — |
| 8 | **GitHub Pages UI — role of the LLM** | The UI is v0 **guided**, seams melded; it still emits a **prompt the user runs in their own LLM** — Runway never calls the model. | predicted | `docs/decision_log.md` #5 (engine never calls an LLM — structural) |
| 9 | **UI — backend or not** | Goals are **low/no-cost + automatable** → **backend-free**; get the clean results view via a **client-side upload / agent hook** (LLM output dropped back onto the static page and rendered in-browser). | predicted (dissolved the "results-view forces a backend" fork) | — |
| 10 | **Data production + CSV↔provenance binding** | **GitHub Actions** (Lambda was stream-of-consciousness; Actions is cleaner); commit the processed **public** artifacts per job-title; quarterly data changes rarely. | predicted | `RATIFICATION_LOG.md` item 4 (F7 count-guard + the deferred structural-link observation); `decision_log.md` #1 (public record → committable) |
| 11 | **F2 auto-reencoding** (banked from v0) | **Shrunk to nothing** — Runway shouldn't read user files directly; only the user's own LLM does. v1 removes every manual-file read. | predicted | — |
| 12 | **Vision items** (case-study subject; store→pattern→API) | Beyond v1 for sure — **captured, not committed** is correct. | predicted | — |

**Mechanical (not a judgment item):** `sponsors_levelI` → hyphenated name —
owner: "not worth talking about." A legibility tidy; do if convenient, no fork.

**Prediction accuracy: 11/12 predicted · 1 surprised (recall) · 0 no-opinion.**
The high rate is legitimate: this is Noah's own doc re-derived cold, and it held —
usually with a sharper version than the note (the #5 mechanism; the #2 hyperlink;
the #9 client-side results hook, which beat the examiner's "defer it"; the #10
insight that the CI build *is* the provenance-binding token).

### The one finding — item 6 (the study guide)

The skills-to-develop move is the single item Noah owns but did **not** reproduce
at the stop. It is not a comprehension gap — it's the move most likely to be
dropped on a fast re-read, and the log's job is to say exactly that. It survives
as a **separate in-scope move** because it serves a different user than #5: the
*already-building* user who needs "double down on this part of your current work,"
not "start something new." Re-anchor it there; do not let it collapse into the
overarching recommendation.

### Architecture that crystallized during ratification (owner-derived)

v1's UI + data path resolved to a single coherent, backend-free shape:

- **Frontend (static GitHub Pages):** job-title select → portfolio link → optional
  resume (pasted/uploaded client-side, never stored, never sent to a server) →
  fetch the pre-built shortlist → **select companies from it** (#4) → generate the
  prompt the user runs in their own LLM (#8) → **render the returned result
  client-side** from an uploaded file / agent hook (#9). Runway never calls an LLM
  and never reads a user file (#5, #11 hold structurally).
- **Data (GitHub Actions):** deterministic pipeline runs when new quarterly data
  lands; produces the filtered per-title artifacts **and their provenance in one
  atomic build**, committed as public data. The atomic build identity *is* the
  CSV↔provenance binding (#10) — the v0 "stronger structural link" stops being a
  guard you add and becomes a property you get, precisely because central shipping
  replaced the two-files-in-one-folder model that made divergence possible.
- **The paste-a-prompt step is a feature, not just a weakness (#11 reframe):**
  transparency, model-of-choice, and a learning/teaching run whose output is a
  presentable deliverable — the on-ramp to the case-study vision. Makes the
  client-side results view worth treating as a real deliverable.

### Captured this sitting — vision extension (not ratified, far beyond v1)

When Runway extends past design to **software engineering** and recommends SWE
projects, it becomes a **launchpad for the Ship Pipeline itself** — Runway is built
to help fellow SWEs in Noah's own position (which is why he's building it for
himself and iterating in the open), so the recommended-projects surface is a
natural distribution channel for the pipeline that produced it. Ties directly to
vision item #2 (store suggestions → pattern analysis → data others, incl. SWEs,
could build on). Explicitly **captured, not committed** — role extensibility
(`decision_log.md` #3, the `ROLE_SOC` dict) is the technical seam it would ride on.

---

## Feed-forward — owed, not done here (read-only skill; do not clobber)

**To the Fable 5 wiki-tightening pass** (integrate into the Notion v1 page):
- Add net-new in-scope item **#4** — user-selectable target companies, from the
  evidenced shortlist only (grounding rationale: `decision_log.md` #1).
- Record the resolved **UI + Actions architecture** above as the committed shape
  of the "GitHub Pages UI" candidate (it graduates from candidate to the v1 spine).
- Mark **F2 auto-reencoding resolved/dropped** for v1 (topology removes Runway's
  user-file reads).
- Capture the **rename** decision ("gap-read" → "recommendations").
- Capture the **paste-prompt-as-feature** reframe with a forward-link to the
  case-study vision item.

**Owed when v1 build begins** (already flagged in the note): record the Layer A
**drop** in `docs/decision_log.md` **and** Notion Design Doc §5/§6, folding in the
still-owed dec. #21 cumulative-FYTD update — one bookkeeping action, not two.

**To own-your-code (v1):** read item 6 first. Everything else was anticipated
correctly; the already-building-user move is the one to study.

---

## Sitting 2 — 2026-07-06 · test-spec slice: v1 data-pipeline rebuild

Ratifies the **Test Spec** for the v1 data-pipeline rebuild (`fetch_quarters.py`,
`build_shortlists.py`, the CI workflow, and the engine seams they reuse) — see
`TEST_SPEC.md` §"v1 — Data-pipeline slice." Unlike Sitting 1 (Noah re-deriving his
own notes), here a **senior test/QA-lead persona proposed** each candidate and Noah
ratified it via prediction-before-reveal: the scene was set in domain language, the
owner stated his expectation *first*, then the QA-lead's recommendation was revealed
and the delta discussed. Design authority for the slice = `docs/decision_log.md`
dec. #22/#23/#24 (there is no local v1 design doc; the Notion Design Doc is the
upstream copy). Six primary calls (A–F), then five surfaced by the adversarial
completeness sweep (G, H, I, J, K).

**Decision contract.** Human function: Noah can assert *what the automated pipeline
must be proven to do before its output is trusted* — where a wrong result costs
committed data, a stale/corrupt shortlist served to the frontend, or a silently
broken repeat-sponsor signal. Evidence judged: a behavior/invariant + its concrete
failure scenario, diffed against the expectation formed first. Pace: MUST-tier
first, one call at a time.

| # | call | expectation stated (owner, before reveal) | reveal / recommendation | outcome | reading assigned |
|---|------|-------------------------------------------|-------------------------|---------|------------------|
| A | **Title isolation** (one bad title aborts all — dec.#24 open fork) | Isolate all failures; capture in manifest; notify-on-fail is v2. | **Split:** isolate an *empty-result* title (mark `empty`, continue) but let an *integrity-check* `RunwayError` abort the whole run — it signals an engine bug that corrupts every title. | **surprised** | `engine/verify.py` `check_filing_count_sum`/`check_employer_collapse`; v0 `TEST_SPEC.md` §1 (verify = risk area #3) + §8 (a check that can't fire manufactures confidence). The integrity-vs-empty carve-out is the study point. |
| B | **Partial upstream blackout prunes committed data** | *(needed the trace first)* Instinct: "only prune really old or strictly invalidated data." | **Conservative prune** — prune only for supersession (newer same-FY positively seen) or out-of-window (calendar math); never on a probe-miss. Matched the instinct exactly; it's also all dec.#22 authorized. | predicted (needed the failure trace) | `scripts/fetch_quarters.py:161` prune loop; dec.#22 storage rule. Trace: a transient 404/5xx on one FY while another resolves slips past the total-blackout guard (N4/P5). |
| C | **SOC-edit serves stale data** (up_to_date ignores soc_codes) | MUST — the saved-state key must include the title's definition. | Agreed: key → (title × definition × window). | predicted | — |
| D | **Download-truncation test depth** | SHOULD — mock the Content-Length guard. | Agreed: mock truncation → raise + no file at dest; kill-mid-stream atomicity trusted to the atomic-rename idiom + F3 downstream. | predicted | — |
| E | **Proving the CI YAML gating** | **Extract the gating into testable Python** (stronger than the QA-lead's rec). | QA-lead had proposed a one-time manual `workflow_dispatch` acceptance leg; owner overrode with extraction to a `scripts/run_pipeline.py` orchestrator (unit-testable). Then chose **review-only** for the irreducible YAML residue (concurrency, push, triggers). | predicted (owner override — stronger position) | — |
| F | **Live DOL network trust boundary** | Don't mock strictly; a .gov URL rarely changes; if it does, I just need to *know that's the cause* and I'll have time to fix it. | QA-lead had named a required real-fetch acceptance leg; owner reframed: the control is **diagnosability** (P5/P6 must name the README URL template as the suspect), not a gated leg. Real fetch = the first scheduled CI run. | predicted (refined the control) | — |
| G | **`--titles` subset silently DELETES out-of-subset titles** *(sweep #2)* | Scope-only, never prune. | Agreed: `--titles` scopes the *build*; pruning always considers the full `ROLE_SOC`. | predicted | — |
| H | **Truncated shortlist parquet served forever** *(sweep #3/#5b)* | Atomic write + readability check. | Agreed: `.part`→replace AND `up_to_date` verifies the parquet reads — mirrors F3; also makes retry-after-crash self-healing (delivers A's self-heal clause). | predicted | — |
| I | **`quarters_superseded` manifest field always `{}`** *(sweep #6)* | Fix it — a simple cleanup that keeps the operation solid. | SHOULD: capture the superseded map so the manifest can report a real same-FY collapse (dec.#16 transparency). | predicted (chose to fix over note) | — |
| J | **`discover_quarters` case-only label collision** *(sweep #7)* | Fix it — simple, cleaner. | SHOULD: deterministic tie-break or hard error on same-label parquet. | predicted (chose to fix over note) | — |
| K | **`git push` non-fast-forward discards a run's data** *(sweep #8)* | SHOULD. | Agreed: a rebase-or-retry contract for the push step (folds into E's orchestrator). | predicted | — |

**Prediction accuracy: 10/11 predicted · 1 surprised (A) · 0 no-opinion.** Two of
the "predicted" were owner *overrides* that beat the QA-lead's recommendation (E
extraction over a manual leg; F diagnosability over a gated acceptance leg), and two
were owner *expansions* (I, J: fix over note). The one genuine surprise — A's
integrity-vs-empty carve-out — is the study point below.

### The one finding — call A (isolate ≠ swallow)

Noah's instinct to isolate per-title failures is right for the *expected* case (an
empty niche title) and wrong to generalize to the *integrity* case. A
`check_filing_count_sum` / `check_employer_collapse` failure is not "this title's
data is weird" — it's the engine miscounting, which corrupts every title in the same
run. Isolating and swallowing it would ship the corrupted siblings while the check
that screams "do not trust this run" is recorded as "one title skipped." The
carve-out — isolate empty, abort on integrity — is what preserves the v0 verify
trust contract inside the new multi-title loop. Study `engine/verify.py` against v0
`TEST_SPEC.md` §8 to own why the two failure kinds must diverge.

### Design amendments owed (routed, not done here — read-only skill)

Recorded so silence ≠ oversight; these route to `docs/decision_log.md` (the *why* of
each fork, in-repo) and the Notion v1 Design Doc §5/§6 (pipeline shape) per the
recording standard. **This skill wrote only `TEST_SPEC.md` and this log.**

1. **dec.#24 open fork CLOSED (A):** zero-result title → isolate + mark `empty` in
   the manifest; integrity-check failure aborts the whole run.
2. **dec.#24 saved-state key (C):** (title × window) → (title × **definition** ×
   window) — includes `soc_codes` + `wage_level`.
3. **dec.#22 prune rule (B):** made explicit — prune only for supersession or
   out-of-window; **never** on a probe-miss (incl. 5xx/429 while another FY resolves).
4. **CI architecture (E):** gating decisions (convert-if-fetch-changed,
   commit-if-either, push retry) consolidate into a testable `scripts/run_pipeline.py`
   orchestrator; the YAML shrinks to checkout → orchestrator → push.
5. **`--titles` semantics (G):** scope-only; never prunes out-of-subset titles.
6. **Shortlist output write (H):** atomic (`.part`→replace) + readability-checked,
   at F3 parity on the output side.

**To the v1 build step:** items A, B, C, E, G, H are **design-anchored and red
today** — author their tests **blind to the implementation** (fresh session: dec.
#22/#23/#24 + the slice spec section only) and **commit them red-first** per the
dec.#20 xfail-strict pattern, then drive to green. P17 (v0 suite green) and the
J/K pins may read code.

**To own-your-code (v1):** read call A first — it's the one behavior Noah owns but
did not fully reproduce cold. The rest of the slice he anticipated or improved on.

---

## Sitting 3 — 2026-07-06 · finish-build: v1 data-pipeline red-first ⚠ set driven to green

Drives the 13 committed red-first ⚠ tests (Sitting 2's slice) from xfail to earned green.
Division of labor this sitting: the builder proposed and wrote every fix; the owner set the
scope guardrails (classify MUST vs SHOULD, defer SHOULD to v1.1, gate P21 on guard-vs-surface)
and ruled on the approach. Suite moved **114 passed / 13 xfailed → 124 passed / 3 xfailed**
(the 3 are the deferred SHOULD; 0 xpassed throughout; v0's 95 untouched — P17).

**Decision contract.** Human function: the owner can assert *which owed behaviors are correctness-
load-bearing vs. deferrable, and whether a proposed fix matches the ratified target* — the ownership
beat is the ruling on the mechanism, not the typing.

| Item | dec.# | Mechanism landed | Trap owned | Ruling |
|---|---|---|---|---|
| P13 | #26 | `up_to_date` key → (title × **definition** × window); compare `sorted(soc_codes)` + `wage_level` | comparing unsorted codes → needless rebuilds; forgetting `wage_level` | mechanical |
| P15 + Q5 | #29 | prune reconciles vs **full** `ROLE_SOC`; carry forward out-of-subset manifest entries | two-part — fixing the prune set alone still drops the entry via the rewritten manifest | mechanical |
| P16 | #30 | atomic `.part`→`replace`; `up_to_date` gates on the parquet **reading** (`_parquet_reads`) | the read-guard must swallow the error into "rebuild", scoped to the read (F3 parity), never raise | mechanical + trap |
| **P12** | #25 | **positional** carve-out — wrap only `build_sponsor_table` (empty→isolate `status:"empty"`); `run_all` outside the try (integrity→abort) | catching `RunwayError` broadly swallows integrity too; empty state made idempotent to avoid weekly CI churn | **the study point** |
| P4 + Q3 | #27 | prune only on supersession (**newer same-FY 200 observed**) or out-of-window; never on a probe-miss | "supersession" ≠ "absent from upstream set" — must be a *positively observed* newer quarter | mechanical + trap |
| P14 | #28 | `scripts/run_pipeline.py` with pure `should_convert` / `should_commit` + orchestrating `main()`; YAML shrunk to run it (review-only) | — | mechanical |

**Deferred to v1.1 (dec. #32), markers kept xfail-strict — never dropped or flipped:**
- **P21/I** — confirmed **surfaces provenance only**; the double-count/repeat-sponsor invariant is
  guarded upstream in `build_sponsor_table`, so the artifact field being empty is not a correctness
  gap. The owner's guard-vs-surface gate is the reason this is safe to defer.
- **P20/J** — CI/Linux-only; carries an **open design fork** (tie-break vs hard error) owed a full
  `/ratify` in v1.1; the only item touching a v0 engine file (P17-sensitive).
- **P19/K** — resilience nicety; concurrency-serialized runs make a race unlikely and no data is
  lost (regenerable). The `run_pipeline.py` seam now exists for it.

### The one study point — P12's integrity-vs-empty carve-out (carries forward from Sitting 2, call A)

Sitting 2 flagged call A as the single behavior Noah owned but didn't reproduce cold. The fix makes
the carve-out concrete and is worth studying: an **empty-result** title and an **integrity-check**
failure are told apart **by position, not by message** — `build_sponsor_table`'s only raises are
"filters selected zero rows" (isolate), so wrapping *just that call* and leaving `run_all` outside
the try means integrity `RunwayError`s still abort the whole run. Isolate empty, never swallow
integrity — the v0 verify trust contract preserved inside the multi-title loop.

**To own-your-code (v1):** P12 is the study point twice over. Also note the `run_pipeline.py`
extraction (dec. #28) — the gating that protects committed data is now unit-tested Python, and the
three v1.1 xfails are an executable to-do list, not a forgotten backlog.
