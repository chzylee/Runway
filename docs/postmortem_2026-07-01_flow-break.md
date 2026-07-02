# Post-mortem — the run-it-yourself flow broke (2026-07-01)

Companion to `decision_log.md`. That log records *what* was decided and why. This
records *why the build diverged from those decisions*, what broke, and — for each
fix — the direction an owning engineer would have given to get the same result.
The point is ownership: you should be able to read this and see that none of these
needed me to catch them. You could have.

---

## The one-sentence root cause

**The build was verified for data integrity but never for the user's actual
run-path**, and one mid-build decision (B2) was implemented in a way that
contradicted the decision itself — so following the documented steps, on the
target user's machine, was guaranteed to crash.

There are two different kinds of "correct" here, and the build nailed one and
ignored the other:

- **Internal correctness** — the engine, the normalization, the provenance, the
  "verification cell." This is genuinely good and was tested.
- **External correctness** — does a non-technical person, on *their* machine,
  following the *written* steps, get a result. This was never exercised once.

The brief's North Star is literally *"UX for non-technical users — the real hard
problem."* The build optimized the engineer's half and skipped the half the brief
named as the hard one.

---

## Why it went awry (process, not just bugs)

1. **A decision was half-implemented, against its own text.** Decision **B2**
   said: use Q1–Q4 for a stronger repeat-sponsor signal, *and* "single quarter
   remains the documented kill-test." The code made four quarters **mandatory**
   and hard-crashed on any missing one — killing the single-quarter path that B2
   itself said must stay valid. The Ledger was right; the code disobeyed the
   Ledger.

2. **The README and the code were never reconciled.** README step 1 says download
   *one* quarter (one URL). The code demanded four. Nobody ran the exact
   documented happy-path top to bottom on a clean machine — if anyone had, it
   fails on line one.

3. **It was only ever run on the builder's machine.** The target user is on a
   Japanese-locale Windows console (cp932). The scripts print Unicode (em-dashes);
   cp932 can't encode them; Python crashes. Invisible on a UTF-8 machine. The one
   environment that mattered was the one never tested.

4. **The error path — the only place a non-technical user meets the tool when
   things go wrong — got zero design.** The failure was a raw traceback naming
   internal functions (`load_certified_rows`, `xlsx_to_parquet`) and advising a
   script that *couldn't* fix the problem. For a "UX for non-technical users"
   product, the error path is not an edge case; it's the product.

5. **A correctness gate was coupled to one dataset.** The golden verify check
   hard-asserted a specific FY2025-Q4 employer (`IGAVEL`). It would have crashed
   the moment the user did the *right* thing and used current data. A gate that
   fails on valid input punishes correct behavior — worse than no gate.

Note what was **in** scope and fine: v1 being "by hand, no app" was per the brief.
The sin isn't that it's script-driven — it's that the script-driven flow
contradicted itself, crashed on the documented path, and spoke in tracebacks.

---

## The defects, in owner-directable form

Each row: what you'd see → how you'd find it yourself → the direction you'd give
me → what I changed.

### 1. Demanded 4 quarters; every doc said 1

- **Symptom:** `FileNotFoundError: Missing parquet for FY2025Q1 …` after doing
  exactly what the README said (download Q4, run the scripts).
- **Diagnose it yourself:** the traceback points at `load_certified_rows`. One
  level up, `build_shortlist.py` had `DEFAULT_QUARTERS = [Q1,Q2,Q3,Q4]`. Cross-check
  against README step 1 ("download *a* quarter") and decision-log **B2** ("single
  quarter remains the documented kill-test"). Three sources say one; code says four.
- **What you'd direct:** *"Use whatever quarters are actually converted; default to
  all present; one is valid; never crash on a quarter I didn't ask for."*
- **Fix:** `detect_quarters()` in `engine/sponsors.py`; `build_shortlist.py` now
  defaults to detected quarters and prints a real message (not a crash) when none
  exist.

### 2. The error named a fix that couldn't work

- **Symptom:** provenance said `[MISSING — run scripts/convert_quarters.py]`, but
  you *ran* that and it changed nothing.
- **Diagnose it yourself:** `convert_quarters.py` only converts xlsx files that are
  *in* `data/raw/`. Q1–Q3 were never downloaded, so converting can't produce them.
  The message named the wrong cause.
- **What you'd direct:** *"When data's missing, tell the user where to download it
  and what filename, not to re-run a converter that has nothing to convert."*
- **Fix:** `no_data_message()` — points at the DOL browse page, the newest quarter,
  the filename pattern, and the one command to run.

### 3. Crashed on a Japanese-locale console (cp932)

- **Symptom:** `UnicodeEncodeError: 'cp932' codec can't encode character '—'`.
- **Diagnose it yourself:** `—` is an em-dash; `cp932` is the JP Windows
  codepage. Python uses the console's locale encoding for `print` and `write_text`
  unless told otherwise. It works on any UTF-8 machine, which is why it slipped.
- **What you'd direct:** *"This must run on my machine, not just yours. Force UTF-8
  everywhere so locale never decides whether it crashes."*
- **Fix:** `sys.stdout/stderr.reconfigure(encoding="utf-8")` guard at the top of
  every script; `run.py` sets `PYTHONUTF8=1` for subprocesses; all file I/O passes
  `encoding="utf-8"`. (Saved to project memory so new scripts inherit it.)

### 4. Verification gate hard-anchored to one quarter's data

- **Symptom:** none yet — a landmine. Using current data would crash the *verify*
  step on `kill-test top sponsor 'IGAVEL' present`.
- **Diagnose it yourself:** `verify.py` asserted a literal employer from FY2025 Q4.
  Ask "what happens to this check when I load FY2026 data?" — it fails on correct input.
- **What you'd direct:** *"A golden value tied to one quarter should only run when
  that quarter is loaded; otherwise skip it, don't fail."*
- **Fix:** `verify_golden_killtest` now skips (with a note) when its anchor quarter
  isn't in the run.

### 5. Report copy hardcoded "/4" and "last fiscal year"

- **Symptom:** with one quarter, the report would say "1/4" and "the last fiscal year."
- **Diagnose it yourself:** grep the report builder for `/4` and "fiscal year";
  both were literals, not derived from the data.
- **What you'd direct:** *"Every number in the report comes from the data actually
  used — never a hardcoded assumption about how much data there is."*
- **Fix:** `build_report.py` derives `n_quarters` and an honest window phrase; a
  single-quarter run says "One quarter … a thin sample."

### 6. No single command; stale, deep-linked data guidance

- **Symptom:** three scripts in a required order; README deep-linked one specific
  (now year-old) file instead of the browsable DOL page. Latest is FY2026 Q2.
- **What you'd direct:** *"One command does the whole pipeline. Point me at the page
  to browse, not a single frozen file."*
- **Fix:** `scripts/run.py` (convert → shortlist → report, with guard rails);
  README rewritten to the DOL performance page + currency note.

---

## If you had owned this from the start

You would not have needed to read the code. Four sentences, from the docs alone,
would have produced every fix above:

1. "The README says one quarter, decision B2 says one quarter must still work — so
   why does the code demand four? Make it run on whatever I have."
2. "It has to run on *my* Windows machine before you call it done."
3. "When it can't find data, it should tell a non-technical person what to do — not
   print a Python traceback."
4. "One command, not three."

That's the whole repair, directed entirely from the brief and the decision log,
without opening a `.py` file. That is what owning it looks like here.

---

## Owner's pre-ship checklist (so this doesn't recur)

- [ ] **Run the README verbatim on a clean machine.** Not the code you remember —
      the steps as written. If step 1 is "download one quarter," do exactly that.
- [ ] **Run it on the target user's environment**, or at least force-neutralize
      environment assumptions (encoding, paths, shell).
- [ ] **Read each decision-log entry against the code.** B2 says X; does the code
      do X? A decision half-implemented is a bug with a paper trail.
- [ ] **Trigger every failure on purpose** (no data, wrong file, partial data) and
      read the message as the non-technical user. Traceback = not shipped.
- [ ] **No literal in the output that assumes the size/shape of the input** (no
      "/4", no "fiscal year") unless it's derived from the data actually used.
- [ ] **No correctness gate tied to one dataset** unless it's guarded to that dataset.
