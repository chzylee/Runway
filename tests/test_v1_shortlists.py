"""v1 slice — build_shortlists.py: per-title incremental build, manifest, prune.

Traces to TEST_SPEC.md §"v1 — Data-pipeline slice" (P7-P10, P12, P13, P15, P16,
P21; Q2, Q5) and Scenario D (§v1.6), grounded on docs/decision_log.md
dec. #24/#25/#26/#29/#30 and dec. #16/#21. Runs in-process against a throwaway
repo (v1_support.build_env); the network is never touched.

⚠ red-first (xfail-strict, dec. #20 pattern) — the design-anchored behaviors the
code does not yet honor, each flagged "currently red" in the decision log:
  P12/A (dec.#25) · P13/C (dec.#26) · P15/G (dec.#29) · P16/H (dec.#30) ·
  P21/I (dec.#16) · Q5/G (dec.#29).
Each MUST fail against today's code before its fix lands (TEST_SPEC §v1.7).
"""
from __future__ import annotations

import pandas as pd
import pytest

import build_shortlists
from engine import RunwayError
from v1_support import build_env, write_selectable_parquet

# The real `design` role definition (engine.ROLE_SOC / dec. #3).
DESIGN_SOC = ["15-1255", "27-1024", "27-1021"]


# =========================================================================== P7
def test_P7_build_emits_changed_to_github_output(tmp_path, monkeypatch):
    """P7 (dec. #22/#24; :143): under GitHub Actions, build writes changed=true|false
    to $GITHUB_OUTPUT so the commit step can gate on 'fetch OR build changed'."""
    out = tmp_path / "gh_output.txt"
    out.write_text("", encoding="utf-8")
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    build_shortlists._emit_github_output(True)
    build_shortlists._emit_github_output(False)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert "changed=true" in lines
    assert "changed=false" in lines


# =========================================================================== P8
def test_P8_new_quarter_rebuilds_all_titles(tmp_path, monkeypatch):
    """P8 (dec. #24; :78): a new quarter shifts the window, so every title rebuilds."""
    env = build_env(tmp_path, monkeypatch, role_soc={"design": DESIGN_SOC})
    write_selectable_parquet(env.processed, "FY2099Q1")
    assert build_shortlists.build_all() is True
    assert env.read_manifest()["window"] == ["FY2099Q1"]

    write_selectable_parquet(env.processed, "FY2100Q1")          # a new fiscal year
    assert build_shortlists.build_all() is True
    manifest = env.read_manifest()
    assert manifest["window"] == ["FY2099Q1", "FY2100Q1"]
    assert manifest["titles"]["design"]["quarters_built_from"] == ["FY2099Q1", "FY2100Q1"]


def test_P8_new_title_builds_only_itself(tmp_path, monkeypatch):
    """P8 (dec. #24; :78): a title added to ROLE_SOC with no stored parquet builds;
    an unchanged title is left untouched (byte-identical)."""
    env = build_env(tmp_path, monkeypatch, role_soc={"design": DESIGN_SOC})
    write_selectable_parquet(env.processed, "FY2099Q1")
    build_shortlists.build_all()
    design_bytes = env.parquet("design").read_bytes()

    monkeypatch.setattr(build_shortlists, "ROLE_SOC",
                        {"design": DESIGN_SOC, "extra": DESIGN_SOC})
    assert build_shortlists.build_all() is True
    assert env.parquet("extra").exists()                        # the new title built
    assert env.parquet("design").read_bytes() == design_bytes   # design NOT rewritten
    assert set(env.read_manifest()["titles"]) == {"design", "extra"}


def test_P8_removed_title_is_pruned(tmp_path, monkeypatch):
    """P8 (dec. #24; :78): a title removed from the FULL ROLE_SOC registry has its
    stored parquet pruned and its manifest entry dropped."""
    env = build_env(tmp_path, monkeypatch,
                    role_soc={"design": DESIGN_SOC, "extra": DESIGN_SOC})
    write_selectable_parquet(env.processed, "FY2099Q1")
    build_shortlists.build_all()
    assert env.parquet("extra").exists()

    monkeypatch.setattr(build_shortlists, "ROLE_SOC", {"design": DESIGN_SOC})
    assert build_shortlists.build_all() is True
    assert not env.parquet("extra").exists()
    assert set(env.read_manifest()["titles"]) == {"design"}


# =========================================================================== P9
def test_P9_idempotent_second_run_writes_no_parquet(tmp_path, monkeypatch):
    """P9 (dec. #24; :103): a second run on unchanged inputs writes no parquet and
    reports changed=False."""
    env = build_env(tmp_path, monkeypatch, role_soc={"design": DESIGN_SOC})
    write_selectable_parquet(env.processed, "FY2099Q1")
    assert build_shortlists.build_all() is True
    pq = env.parquet("design")
    before = pq.read_bytes()
    mtime = pq.stat().st_mtime_ns

    assert build_shortlists.build_all() is False
    assert pq.read_bytes() == before
    assert pq.stat().st_mtime_ns == mtime


# =========================================================================== Q2
def test_Q2_build_is_idempotent_over_repeated_runs(tmp_path, monkeypatch):
    """Q2 (invariant, anchors P9): repeated runs converge — only the first writes,
    the rest are no-ops, and the manifest window is stable."""
    env = build_env(tmp_path, monkeypatch, role_soc={"design": DESIGN_SOC})
    write_selectable_parquet(env.processed, "FY2099Q1")
    results = [build_shortlists.build_all() for _ in range(3)]
    assert results == [True, False, False]
    assert env.read_manifest()["window"] == ["FY2099Q1"]


# =========================================================================== P10
def test_P10_manifest_consistent_and_frontend_readable(tmp_path, monkeypatch):
    """P10 (dec. #24; :126): the manifest records the window and, per title, the SOC
    codes / counts / parquet name that were actually built — and the named parquet
    reads back with employer_groups rows (frontend-readable)."""
    env = build_env(tmp_path, monkeypatch, role_soc={"design": DESIGN_SOC})
    write_selectable_parquet(env.processed, "FY2099Q1")
    build_shortlists.build_all()

    manifest = env.read_manifest()
    assert manifest["window"] == ["FY2099Q1"]
    entry = manifest["titles"]["design"]
    assert entry["soc_codes"] == sorted(DESIGN_SOC)
    assert entry["wage_level"] == "I"
    assert entry["parquet"] == "design_levelI.parquet"
    assert isinstance(entry["employer_groups"], int) and entry["employer_groups"] >= 1
    assert isinstance(entry["filings"], int) and entry["filings"] >= 1

    table = pd.read_parquet(env.shortlists / entry["parquet"])
    assert len(table) == entry["employer_groups"]
    assert int(table["filing_count"].sum()) == entry["filings"]


# ======================================================================== P12 ⚠
@pytest.mark.xfail(
    reason="dec.#25 (call A): an empty-result title raises inside build_sponsor_table "
           "and aborts the whole build; there is no per-title isolation yet. Red-first "
           "on the empty-isolation half (the integrity-abort half is already correct — "
           "see test_P12_integrity_check_failure_aborts_whole_run).",
    strict=True,
)
def test_P12_empty_result_title_isolated_others_still_build(tmp_path, monkeypatch):
    """P12/A (dec. #25): a title whose SOC codes match zero certified Level-I filings
    is a normal outcome for a thin niche role — it must be isolated (marked `empty` in
    the manifest) while every other title still builds."""
    env = build_env(tmp_path, monkeypatch,
                    role_soc={"design": DESIGN_SOC, "empty": ["99-9999"]})
    write_selectable_parquet(env.processed, "FY2099Q1")
    build_shortlists.build_all()                                # target: no raise
    assert env.parquet("design").exists()                       # sibling still built
    assert env.read_manifest()["titles"]["empty"]["status"] == "empty"


def test_P12_integrity_check_failure_aborts_whole_run(tmp_path, monkeypatch):
    """P12/A (dec. #25): the OTHER half of the split — an integrity-check RunwayError
    (check_filing_count_sum / check_employer_collapse) means the engine is miscounting,
    which corrupts every title, so it must still ABORT the whole run and ship nothing.

    Fault-injected via run_all (the real integrity path is not data-forceable) to pin
    that build_all does not swallow a verify failure — the constraint the future
    empty-isolation refactor must not violate (isolate empty ≠ swallow integrity)."""
    env = build_env(tmp_path, monkeypatch, role_soc={"design": DESIGN_SOC})
    write_selectable_parquet(env.processed, "FY2099Q1")

    def integrity_failure(table, stats, quarters):
        raise RunwayError("filing_count sums to 4 but 5 rows were selected - "
                          "the aggregation dropped or duplicated filings. Do not trust this run.")

    monkeypatch.setattr(build_shortlists, "run_all", integrity_failure)
    with pytest.raises(RunwayError) as excinfo:
        build_shortlists.build_all()
    assert "do not trust this run" in str(excinfo.value).lower()
    assert not env.manifest_path.exists()                       # nothing shipped


# ======================================================================== P13 ⚠
@pytest.mark.xfail(
    reason="dec.#26 (call C): up_to_date compares only the window (build_shortlists.py:103) "
           "and ignores the stored soc_codes, so editing a title's SOC without a new "
           "quarter is not detected and the title is not rebuilt. Red-first.",
    strict=True,
)
def test_P13_soc_edit_without_new_quarter_rebuilds_title(tmp_path, monkeypatch):
    """P13/C (dec. #26): the saved-state key must be (title × definition × window).
    Editing ROLE_SOC['design'] with the same window must mark the title not-saved and
    rebuild it against the new definition."""
    env = build_env(tmp_path, monkeypatch, role_soc={"design": DESIGN_SOC})
    write_selectable_parquet(env.processed, "FY2099Q1")
    build_shortlists.build_all()

    monkeypatch.setattr(build_shortlists, "ROLE_SOC", {"design": ["15-1255"]})
    build_shortlists.build_all()
    entry = env.read_manifest()["titles"]["design"]
    assert entry["soc_codes"] == ["15-1255"]                    # rebuilt to new definition


# ======================================================================== P15 ⚠
@pytest.mark.xfail(
    reason="dec.#29 (call G): the stale-prune loop is set(prior) - set(built-this-run) "
           "with 'built' scoped by --titles (build_shortlists.py:119), so a scoped run "
           "deletes out-of-subset titles and drops their manifest entries. Red-first.",
    strict=True,
)
def test_P15_titles_scopes_build_only_never_prunes_out_of_subset(tmp_path, monkeypatch):
    """P15/G (dec. #29): --titles restricts only which titles are BUILT; pruning always
    reconciles against the full ROLE_SOC. A scoped run must never delete a title outside
    the subset."""
    env = build_env(tmp_path, monkeypatch,
                    role_soc={"design": DESIGN_SOC, "extra": DESIGN_SOC})
    write_selectable_parquet(env.processed, "FY2099Q1")
    build_shortlists.build_all()
    assert env.parquet("extra").exists()

    build_shortlists.build_all(only_titles=["design"])          # scope to design only
    assert env.parquet("extra").exists(), "--titles must not delete an out-of-subset title"
    assert "extra" in env.read_manifest()["titles"]


# ======================================================================== Q5 ⚠
@pytest.mark.xfail(
    reason="dec.#29 (Q5/G): a --titles subset run rewrites the manifest with only the "
           "subset, shrinking the title set below ROLE_SOC ∩ prior-manifest. Red-first.",
    strict=True,
)
def test_Q5_titles_subset_never_shrinks_manifest_title_set(tmp_path, monkeypatch):
    """Q5 (invariant, anchors P15/G): --titles never shrinks the manifest's title set
    relative to ROLE_SOC ∩ prior-manifest."""
    env = build_env(tmp_path, monkeypatch,
                    role_soc={"design": DESIGN_SOC, "extra": DESIGN_SOC})
    write_selectable_parquet(env.processed, "FY2099Q1")
    build_shortlists.build_all()
    prior = set(env.read_manifest()["titles"])

    build_shortlists.build_all(only_titles=["design"])
    after = set(env.read_manifest()["titles"])
    assert after >= (prior & {"design", "extra"}), "manifest title set must not shrink"


# ======================================================================== P16 ⚠
@pytest.mark.xfail(
    reason="dec.#30 (call H): up_to_date checks only that the parquet EXISTS "
           "(build_shortlists.py:102) and writes are non-atomic (:63), so a truncated/"
           "corrupt shortlist parquet is trusted and served forever. Red-first — needs "
           "a readability check (+ atomic .part write) so a retry self-heals.",
    strict=True,
)
def test_P16_corrupt_shortlist_parquet_is_rebuilt_not_served(tmp_path, monkeypatch):
    """P16/H (dec. #30): mirror F3 on the output side. A parquet left truncated by a
    killed mid-write must be detected as unreadable and rebuilt on the next run, not
    skipped and served — retry-after-crash self-heals."""
    env = build_env(tmp_path, monkeypatch, role_soc={"design": DESIGN_SOC})
    write_selectable_parquet(env.processed, "FY2099Q1")
    build_shortlists.build_all()
    pq = env.parquet("design")

    pq.write_bytes(b"truncated-not-a-parquet-file")             # a killed-mid-write artifact
    build_shortlists.build_all()                                # target: detect + rebuild
    pd.read_parquet(pq)                                         # must read cleanly (self-healed)


# ======================================================================== P21 ⚠
@pytest.mark.xfail(
    reason="dec.#16 (call I): build_all discards the real superseded map "
           "(kept, _ = supersede_...(quarters) at build_shortlists.py:88) and _build_one "
           "re-superseds already-collapsed data, so manifest quarters_superseded is "
           "always empty. Red-first — capture the map, don't discard it.",
    strict=True,
)
def test_P21_manifest_reports_real_same_fy_supersession(tmp_path, monkeypatch):
    """P21/I (dec. #16): two SAME-FY quarters (FY2099 Q1 + Q2) are a real cumulative
    collapse — Q1 is superseded by the cumulative Q2. The manifest must report that
    collapse in quarters_superseded, not an empty map."""
    env = build_env(tmp_path, monkeypatch, role_soc={"design": DESIGN_SOC})
    write_selectable_parquet(env.processed, "FY2099Q1")
    write_selectable_parquet(env.processed, "FY2099Q2")         # cumulative: supersedes Q1
    build_shortlists.build_all()
    entry = env.read_manifest()["titles"]["design"]
    assert entry["quarters_superseded"] == {"FY2099Q1": "FY2099Q2"}


# ==================================================================== Scenario D
def test_ScenarioD_incremental_proof(tmp_path, monkeypatch):
    """Scenario D (§v1.6) — the in-suite acceptance leg: seed FY(n-1)+FY(n), then walk
    build -> no-op -> add-title -> advance-window -> remove-title, asserting each
    incremental trigger fires exactly. (Scenario C, the live-DOL fetch, is the reserved
    real-data leg and is deliberately never in the suite; the prune-safety and --titles
    scoping halves of Scenario D are their own red-first tests, P4 and P15.)"""
    env = build_env(tmp_path, monkeypatch, role_soc={"design": DESIGN_SOC})
    write_selectable_parquet(env.processed, "FY2099Q1")
    write_selectable_parquet(env.processed, "FY2100Q1")

    # 1. first build produces the shortlist
    assert build_shortlists.build_all() is True
    assert env.parquet("design").exists()
    design_bytes = env.parquet("design").read_bytes()

    # 2. second run on unchanged inputs is a clean no-op
    assert build_shortlists.build_all() is False
    assert env.parquet("design").read_bytes() == design_bytes

    # 3. adding a title builds only it; the unchanged title is untouched
    monkeypatch.setattr(build_shortlists, "ROLE_SOC",
                        {"design": DESIGN_SOC, "illustration": DESIGN_SOC})
    assert build_shortlists.build_all() is True
    assert env.parquet("illustration").exists()
    assert env.parquet("design").read_bytes() == design_bytes

    # 4. advancing the window (a new FY drops in) rebuilds every title
    write_selectable_parquet(env.processed, "FY2101Q1")
    assert build_shortlists.build_all() is True
    manifest = env.read_manifest()
    assert manifest["window"] == ["FY2099Q1", "FY2100Q1", "FY2101Q1"]
    for title in ("design", "illustration"):
        assert manifest["titles"][title]["quarters_built_from"] == \
            ["FY2099Q1", "FY2100Q1", "FY2101Q1"]

    # 5. removing a title from ROLE_SOC prunes its stored parquet
    monkeypatch.setattr(build_shortlists, "ROLE_SOC", {"design": DESIGN_SOC})
    assert build_shortlists.build_all() is True
    assert not env.parquet("illustration").exists()
    assert set(env.read_manifest()["titles"]) == {"design"}
