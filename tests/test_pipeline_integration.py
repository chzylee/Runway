"""Fixture-integration tests: the committed ~20-row DOL-shaped xlsx driven
through the REAL scripts as a subprocess in an isolated tmp mini-repo.

Covers M8, M9 (CLI contract), M12, M14-M16, F1, F2, F3, F5, P1. The WARN items
(F1, F2, F3, F5) were committed as xfail(strict) to pin ratified behavior the
code lacked; stage 6 (finish-build) built each and removed its marker (dec. #21).
They now assert green.

The suite runs entirely on synthetic data (ratified J3): a fresh clone tests
everything with no 100 MB download.
"""
from __future__ import annotations

import json
import os
import sys

import pandas as pd
import pytest

import dol_xlsx
from conftest import assert_no_traceback

FIXTURE = dol_xlsx.FIXTURE_PATH
EXPECTED = dol_xlsx.EXPECTED


def _full_run(env):
    """Place the fixture and run the whole pipeline once; return the process."""
    env.place_fixture(FIXTURE)
    return env.run("run.py", expect_ok=True)


# =========================================================================== M8
def test_M8_conversion_resolves_columns_by_name_and_counts_padding(pipeline_env):
    """M8 (dec. #6, #16): columns resolved by NAME from a shuffled+decoy header;
    empty padding rows dropped AND counted; parquet named from the filename."""
    env = pipeline_env
    env.place_fixture(FIXTURE)
    proc = env.run("convert_quarters.py", expect_ok=True)
    assert "skipped 2 empty padding rows" in proc.stdout
    parquet = env.processed / "lca_fy2099q1.parquet"        # label from filename
    assert parquet.exists()
    df = pd.read_parquet(parquet)
    assert len(df) == EXPECTED["rows_total"]                # padding excluded
    from engine.sponsors import REQUIRED_COLUMNS
    assert list(df.columns) == REQUIRED_COLUMNS             # by name, not position


def test_M8_mtime_skip_then_force_reconvert(pipeline_env):
    """M8 (dec. #7): an up-to-date parquet is skipped; --force-convert rebuilds."""
    env = pipeline_env
    env.place_fixture(FIXTURE)
    env.run("convert_quarters.py", expect_ok=True)
    second = env.run("convert_quarters.py", expect_ok=True)
    assert "is up to date" in second.stdout
    forced = env.run("convert_quarters.py", "--force-convert", expect_ok=True)
    assert "streaming" in forced.stdout                     # reconverted


def test_M8_temp_lock_file_ignored_and_misnamed_skipped(pipeline_env):
    """M8: an Excel ~$ lock file is ignored; a non-DOL-named xlsx is skipped
    with a message (SHOULD)."""
    env = pipeline_env
    env.place_fixture(FIXTURE)
    (env.raw / "~$LCA_Disclosure_Data_FY2099_Q1.xlsx").write_bytes(b"lock")
    dol_xlsx.write_xlsx(env.raw / "random_notes.xlsx", [dol_xlsx.row()])
    proc = env.run("convert_quarters.py", expect_ok=True)
    assert "skipping random_notes.xlsx" in proc.stdout
    parquets = list(env.processed.glob("*.parquet"))
    assert [p.name for p in parquets] == ["lca_fy2099q1.parquet"]  # only the real one


# ==================================================================== M9 (CLI)
def test_M9_cli_empty_raw_exits_1_plain_english_no_traceback(pipeline_env):
    """M9 (dec. #15): empty data/raw -> exit 1, plain no-data message, no stack
    trace (Scenario B, the failure face)."""
    proc = pipeline_env.run("run.py", expect_ok=False)
    assert_no_traceback(proc)
    assert "No converted LCA data" in proc.stderr


def test_M9_cli_perm_file_rejected_no_traceback(pipeline_env):
    """M9 (dec. #15, S4): a DOL-named file with PERM columns is rejected by the
    required-columns check — plain English, exit 1, no traceback."""
    env = pipeline_env
    perm_row = {c: "x" for c in dol_xlsx.PERM_HEADER}
    dol_xlsx.write_xlsx(env.raw / "LCA_Disclosure_Data_FY2099_Q1.xlsx",
                        [perm_row], header=dol_xlsx.PERM_HEADER)
    proc = env.run("run.py", expect_ok=False)
    assert_no_traceback(proc)
    assert "PERM" in proc.stderr


# =========================================================================== M12
def test_M12_hiring_now_created_blank(pipeline_env):
    """M12 (dec. #4): the tool creates hiring_now.csv blank, with the template
    columns."""
    env = pipeline_env
    _full_run(env)
    assert env.hiring_now.exists()
    hn = pd.read_csv(env.hiring_now, dtype=str).fillna("")
    assert list(hn.columns) == ["employer", "employer_display", "hiring_now", "notes"]
    assert (hn["hiring_now"] == "").all()                   # blank


def test_M12_hiring_now_never_overwritten_and_values_reach_report(pipeline_env):
    """M12 (dec. #4): a hand-edited hiring_now.csv is left byte-identical on
    re-run, and its values reach the report."""
    env = pipeline_env
    _full_run(env)
    hn = pd.read_csv(env.hiring_now, dtype=str).fillna("")
    hn.loc[0, "hiring_now"] = "yes"
    hn.loc[0, "notes"] = "Careers page open"
    display = hn.loc[0, "employer_display"]
    hn.to_csv(env.hiring_now, index=False, encoding="utf-8", lineterminator="\n")
    edited_bytes = env.hiring_now.read_bytes()

    env.run("build_report.py", expect_ok=True)

    assert env.hiring_now.read_bytes() == edited_bytes      # never overwritten
    html = env.report.read_text(encoding="utf-8")
    assert "Careers page open" in html                      # value reached report
    assert display in html


def test_M12_stale_hiring_now_keys_ignored(pipeline_env):
    """M12 (dec. #4): keys no longer in the shortlist are ignored without a
    crash (the staleness warning gap is a logged design observation, J4)."""
    env = pipeline_env
    _full_run(env)
    hn = pd.read_csv(env.hiring_now, dtype=str).fillna("")
    hn.loc[len(hn)] = ["GHOST EMPLOYER", "Ghost LLC", "yes", "not in shortlist"]
    hn.to_csv(env.hiring_now, index=False, encoding="utf-8", lineterminator="\n")
    proc = env.run("build_report.py", expect_ok=True)
    assert_no_traceback(proc)


def test_M12_broken_hiring_now_columns_error(pipeline_env):
    """M12 (dec. #4): a hiring_now.csv missing a required column stops with an
    instructive message, exit 1, no traceback."""
    env = pipeline_env
    _full_run(env)
    env.hiring_now.write_text("foo,bar\n1,2\n", encoding="utf-8")
    proc = env.run("build_report.py", expect_ok=False)
    assert_no_traceback(proc)
    assert "hiring_now.csv is missing column" in proc.stderr


# =========================================================================== M14
def test_M14_report_renders_every_row_notes_and_caveats(pipeline_env):
    """M14 (§6, §2, dec. #13): every employer row (no truncation), single-quarter
    note (1 quarter), wage-excluded note (>0), a missing wage as an em dash, and
    all five caveats verbatim."""
    env = pipeline_env
    _full_run(env)
    html = env.report.read_text(encoding="utf-8")

    for display in EXPECTED["employers"]:
        assert display in html                              # no truncation
    assert "Single-quarter run" in html                     # exactly one quarter loaded
    assert f"{EXPECTED['rows_wage_excluded']} filing(s)" in html
    assert "<td class=\"num\">&mdash;</td>" in html         # Blank Fields' missing wage
    # Pin that the MEDIAN (not min/max) reaches the wage cell: 68,500 and 81,800
    # are each only the median of their row (min/max differ), so a wiring swap fails.
    assert "$68,500" in html                                # Wage Variety median
    assert "$81,800" in html                                # Café Studio median
    for caveat in dol_xlsx_caveats():
        assert caveat in html


def dol_xlsx_caveats():
    # The five ratified caveats, hardcoded (see test_report_unit.test_M14_five_caveats_verbatim).
    return [
        "An LCA certification is not a hire or an open role.",
        "OPT is not sponsorship — a new grad's first job is on OPT; sponsorship comes 1-3 years later.",
        "Design roles are likely not STEM-OPT eligible -&gt; roughly a 12-month OPT window, not 36.",
        "Employer names are conservatively normalized and may under-merge.",
        "Career/portfolio guidance, not immigration legal advice.",
    ]


def test_M14_no_single_quarter_note_with_two_quarters(pipeline_env):
    """M14: the single-quarter note is absent once two quarters are loaded.

    The two quarters are DIFFERENT fiscal years (FY2099Q1 + FY2100Q1): DOL files
    are cumulative FYTD, so two same-FY quarters collapse to the latter one
    (supersede, dec. #21 / F1), which would leave a single quarter and re-trigger
    the note. Distinct fiscal years are the real multi-period signal."""
    env = pipeline_env
    env.place_fixture(FIXTURE)
    dol_xlsx.write_xlsx(env.raw / "LCA_Disclosure_Data_FY2100_Q1.xlsx",
                        [dol_xlsx.row(EMPLOYER_NAME="Second Year LLC")])
    env.run("run.py", expect_ok=True)
    html = env.report.read_text(encoding="utf-8")
    assert "Single-quarter run" not in html


# =========================================================================== M15
def test_M15_artifacts_are_utf8_with_unicode_employer(pipeline_env):
    """M15 (dec. #14): the CSV and HTML are UTF-8 and preserve a non-ASCII
    employer name."""
    env = pipeline_env
    _full_run(env)
    csv_text = env.csv.read_bytes().decode("utf-8")         # decodes as UTF-8
    assert "Café Studio LLC" in csv_text
    html = env.report.read_bytes().decode("utf-8")
    assert "Café Studio LLC" in html


def test_M15_run_survives_cp932_parent_environment(pipeline_env):
    """M15 (dec. #14): a run launched from a cp932 (JP-locale) parent environment
    exits 0 and still emits correct UTF-8 artifacts. (End-to-end smoke only — the
    success path prints no non-ASCII, so the console-reconfigure MECHANISM is
    pinned separately by test_M15_force_utf8_reconfigures_console below.)"""
    env = pipeline_env
    env.place_fixture(FIXTURE)
    proc = env.run("run.py", env={"PYTHONIOENCODING": "cp932"}, expect_ok=True)
    assert_no_traceback(proc)
    assert "Café Studio LLC" in env.csv.read_bytes().decode("utf-8")


def test_M15_force_utf8_reconfigures_console(monkeypatch):
    """M15 (dec. #14): force_utf8() — the mechanism that stops a cp932 console
    from crashing a run whose error message interpolates non-ASCII data — must
    reconfigure BOTH stdio streams to UTF-8 (errors='replace') and set PYTHONUTF8.
    Pinned directly because the end-to-end run cannot observe it (§8.3 review)."""
    import _util
    reconfigured = []

    class FakeStream:
        encoding = "cp932"

        def reconfigure(self, **kwargs):
            reconfigured.append(kwargs)

    monkeypatch.setattr(sys, "stdout", FakeStream())
    monkeypatch.setattr(sys, "stderr", FakeStream())
    monkeypatch.delenv("PYTHONUTF8", raising=False)

    _util.force_utf8()

    assert reconfigured == [{"encoding": "utf-8", "errors": "replace"}] * 2
    assert os.environ.get("PYTHONUTF8") == "1"


# =========================================================================== M16
def test_M16_provenance_complete_and_consistent_with_csv(pipeline_env):
    """M16 (§7): the provenance JSON is complete and agrees with the CSV it
    accompanies."""
    env = pipeline_env
    _full_run(env)
    prov = json.loads(env.provenance.read_text(encoding="utf-8"))
    table = pd.read_csv(env.csv, encoding="utf-8")

    assert prov["employer_groups"] == len(table) == EXPECTED["employer_groups"]
    assert prov["funnel"]["rows_selected"] == int(table["filing_count"].sum()) == EXPECTED["rows_selected"]
    for key, value in EXPECTED.items():
        if key in prov["funnel"]:
            assert prov["funnel"][key] == value
    assert prov["quarters_used"] == ["FY2099Q1"]
    assert prov["distinct_raw_employer_spellings"] == EXPECTED["distinct_raw_employers"]
    assert prov["rows_wage_excluded_from_wage_stats"] == EXPECTED["rows_wage_excluded"]
    assert prov["filters"]["soc_codes"] == ["15-1255", "27-1024", "27-1021"]
    assert len(prov["caveats"]) == 5


# ============================================================================ F1
def test_F1_cumulative_same_fy_overlap_not_double_counted(pipeline_env):
    """F1 (WARN): two overlapping same-FY (cumulative) quarter files must not
    double-count a shared filing nor invent a repeat sponsor."""
    env = pipeline_env
    shared = dol_xlsx.row(EMPLOYER_NAME="Solo Design LLC", WAGE_RATE_OF_PAY_FROM="80000")
    dol_xlsx.write_xlsx(env.raw / "LCA_Disclosure_Data_FY2099_Q1.xlsx",
                        [shared, dol_xlsx.row(EMPLOYER_NAME="Alpha Studio LLC")])
    # Q2 is the later, cumulative file: it re-lists Solo's filing plus a new one.
    dol_xlsx.write_xlsx(env.raw / "LCA_Disclosure_Data_FY2099_Q2.xlsx",
                        [shared, dol_xlsx.row(EMPLOYER_NAME="Alpha Studio LLC"),
                         dol_xlsx.row(EMPLOYER_NAME="Beta Studio LLC")])
    env.run("run.py", expect_ok=True)
    table = pd.read_csv(env.csv, encoding="utf-8")
    solo = table[table["employer"] == "SOLO DESIGN"].iloc[0]
    assert int(solo["filing_count"]) == 1                   # counted once, not twice
    assert solo["repeat_sponsor"] == "no"                   # not a fabricated repeat


# ============================================================================ F2
@pytest.mark.parametrize("target", ["gap_read_filled.md", "hiring_now.csv"])
def test_F2_non_utf8_manual_input_stops_plainly(pipeline_env, target):
    """F2 (WARN): a non-UTF-8 manual input stops with a plain-English error that
    names the file, not a traceback."""
    env = pipeline_env
    _full_run(env)
    path = env.private / target
    if target == "gap_read_filled.md":
        path.write_bytes("# 日本語の見出し\n本文\n".encode("cp932"))
    else:
        path.write_bytes(
            "employer,employer_display,hiring_now,notes\n"
            "WAGE VARIETY,Wage Variety LLC,yes,カフェ\n".encode("cp932"))
    proc = env.run("build_report.py", expect_ok=False)
    assert_no_traceback(proc)
    assert target in proc.stderr


# ============================================================================ F3
def test_F3_unreadable_parquet_stops_plainly(pipeline_env):
    """F3 (WARN): a corrupted parquet stops with a plain-English error naming
    --force-convert, never a traceback."""
    env = pipeline_env
    _full_run(env)
    (env.processed / "lca_fy2099q1.parquet").write_bytes(b"this is not a parquet file")
    proc = env.run("build_shortlist.py", expect_ok=False)
    assert_no_traceback(proc)
    assert "--force-convert" in proc.stderr


# ============================================================================ F5
def test_F5_blank_csv_cell_renders_blank_not_nan(pipeline_env):
    """F5 (WARN, SHOULD): a blank cell in the shortlist CSV must render blank in
    the report, never 'nan' (Blank Fields Co has an empty soc_titles)."""
    env = pipeline_env
    _full_run(env)
    html = env.report.read_text(encoding="utf-8")
    assert "<td>nan</td>" not in html


# ============================================================================ P1
def test_P1_parquet_roundtrips_unicode_blanks_long_strings(tmp_path):
    """P1 (SHOULD, promoted from SKIP #3): the parquet layer round-trips unicode,
    blank, and long-string cells faithfully (as convert writes: dtype='string')."""
    long_str = "A" * 500
    df = pd.DataFrame(
        {"EMPLOYER_NAME": ["Café Studio LLC", "", long_str, "株式会社デザイン"]},
        dtype="string",
    )
    path = tmp_path / "lca_fy2099q1.parquet"
    df.to_parquet(path, index=False)
    back = pd.read_parquet(path)
    assert back["EMPLOYER_NAME"].tolist() == df["EMPLOYER_NAME"].tolist()
