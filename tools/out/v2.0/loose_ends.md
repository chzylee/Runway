# Cross-model onboarding read — loose ends (v2.0)

Reviewer model: Sonnet 5 (cross-model onboarding read) · run 2026-07-01

1. ****What's loose:** §7 "Cross-model onboarding read" is entirely empty — it's a stub describing its own method with no actual findings.**  
   - Where: §7.  
   - Severity: friction.  
   - Fix: Either populate it with real findings before shipping this doc, or delete the section and its cross-references until it has content.
2. **when the fixture quarter is absent — the exact user-visible output is undefined.**  
   - Where: §4 D3, and First Change #1.  
   - Severity: friction.  
   - Fix: Add one sentence specifying the skip-state's console output, e.g. "prints `GOLDEN CHECK: skipped (FY2025Q4 not in quarters)` instead of a PASS/FAIL line."
3. ****What's loose:** The doc asserts `requests>=2.31` is "never imported" as a flat fact but doesn't say how this was verified — "confirm nothing imports it — it doesn't" is circular.**  
   - Where: §5 Drift / First Change #3.  
   - Severity: polish.  
   - Fix: Add "(`grep -r requests engine/ scripts/` returns nothing)" so the claim is self-verifying.
4. ****What's loose:** The bug-fix drill asks "the shortlist has a company listed twice... what's the first thing you'd try?" but the doc never actually answers it.**  
   - Where: §8 Drills, "Bug-fix drill."  
   - Severity: blocker (this is the doc's own stated calibration test, and it doesn't self-answer).  
   - Fix: Add the concrete first-try step as the drill's answer key: run both names through `normalize_employer` (`sponsors.py:94`) by hand; if they produce different `EMP_NORM`, check `_CORP_SUFFIXES` (`:71`) against the actual strings.
5. ****What's loose:** Nothing states whether `build_report` ever touches `sponsors_levelI_rows.csv`, or whether it's purely consumed by the manual portfolio-review step.**  
   - Where: §2 "Final output" / §4 D (report role).  
   - Severity: polish.  
   - Fix: Add one clause to D's "How it works": "reads only `sponsors_levelI.csv`, never `_rows.csv`."
6. ****What's loose:** D2's "Rebuild path" says to run `rapidfuzz` and "watch a false merge appear," but doesn't give a concrete pair.**  
   - Where: §4 D2 "Rebuild path."  
   - Severity: polish.  
   - Fix: Name one real/plausible false-merge pair (reuse "Apple Inc / Apple Bank" from the self-interview for consistency).
7. **.**  
   - Where: Domain primer ("iGavel") / §4 D3.  
   - Severity: friction.  
   - Fix: One clause naming the selection logic (Q4 kill-test's top single-quarter filer, not the full-year #1).
