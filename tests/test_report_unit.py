"""Report-side unit tests: the markdown renderer, money formatting, the
caveat set, the gap-read placeholder gate, and the generation-consistency guard.

Covers M13, M14 (unit-testable parts), F4, F7. The WARN items (F4, F7, and the
M13 href-attribute breakout) were committed as xfail(strict) to pin ratified
behavior the code lacked; stage 6 (finish-build) built each and removed its
marker (dec. #21). They now assert green.
"""
from __future__ import annotations

import json

import pandas as pd
import pytest

import build_report
from _util import CAVEATS
from engine import RunwayError

md = build_report.markdown_to_html


# -------------------------------------------------------------------------- M13
def test_M13_headings_are_demoted():
    """M13 (dec. #17): # -> h3, ## -> h4, ### -> h5 so the injected gap read
    nests under the report's own structure."""
    assert "<h3>Top</h3>" in md("# Top")
    assert "<h4>Sub</h4>" in md("## Sub")
    assert "<h5>Deep</h5>" in md("### Deep")


def test_M13_lists_bold_and_links_render():
    """M13: bullet + numbered lists, bold, and http(s) links render."""
    assert "<ul>\n<li>a</li>\n</ul>" in md("- a")
    assert "<ol>\n<li>one</li>\n</ol>" in md("1. one")
    assert "<strong>x</strong>" in md("**x**")
    assert '<a href="https://a.com/p">text</a>' in md("[text](https://a.com/p)")


def test_M13_script_tag_is_inert():
    """M13/J5: raw HTML in the gap read is escaped, never live."""
    out = md("<script>alert(1)</script>")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_M13_javascript_url_not_linkified():
    """M13/J5: a javascript: URL is never turned into a live link; it stays as
    inert escaped text."""
    out = md("[x](javascript:alert(1))")
    assert 'href="javascript:' not in out
    assert "javascript:alert(1)" in out  # preserved, but only as text


def test_M13_href_attribute_breakout_is_impossible():
    """M13/J5 (WARN): a double-quote inside the URL must not break out of the
    href attribute into a live event handler."""
    out = md('[x](https://a.com/"onmouseover="alert(1))')
    assert 'onmouseover="' not in out


# -------------------------------------------------------------------------- M14
def test_M14_missing_wage_renders_mdash():
    """M14 (§6): a missing wage renders as an em dash, never blank or 'nan'."""
    assert build_report._money(float("nan")) == "&mdash;"
    assert build_report._money(85000) == "$85,000"


def test_M14_five_caveats_verbatim():
    """M14 (§2, dec. #13): exactly the five applicant-facing caveats, verbatim.
    Hardcoded here so any edit to the wording trips the test (they are ratified
    as immigration-sensitive, §5)."""
    expected = [
        "An LCA certification is not a hire or an open role.",
        "OPT is not sponsorship — a new grad's first job is on OPT; sponsorship comes 1-3 years later.",
        "Design roles are likely not STEM-OPT eligible -> roughly a 12-month OPT window, not 36.",
        "Employer names are conservatively normalized and may under-merge.",
        "Career/portfolio guidance, not immigration legal advice.",
    ]
    assert list(CAVEATS) == expected


# --------------------------------------------------------------------- F4 (gap read gate)
def _set_gap(monkeypatch, tmp_path, text):
    p = tmp_path / "gap_read_filled.md"
    if text is not None:
        p.write_text(text, encoding="utf-8")
    monkeypatch.setattr(build_report, "GAP_READ_PATH", p)


def test_gap_read_absent_is_pending(monkeypatch, tmp_path):
    """M13/§3 support: no gap-read file -> visible placeholder, run succeeds."""
    _set_gap(monkeypatch, tmp_path, None)
    body, pending = build_report._gap_read_section()
    assert pending is True
    assert "pending review" in body.lower()


def test_gap_read_present_renders(monkeypatch, tmp_path):
    """M13 support: a filled gap read is injected (not pending)."""
    _set_gap(monkeypatch, tmp_path, "# Project One\n\nDo the thing.")
    body, pending = build_report._gap_read_section()
    assert pending is False
    assert "<h3>Project One</h3>" in body


def test_F4_empty_gap_read_behaves_as_absent(monkeypatch, tmp_path):
    """F4 (WARN): a whitespace-only gap read must behave as absent — placeholder,
    never a silent blank flagship section."""
    _set_gap(monkeypatch, tmp_path, "   \n\t\n   ")
    _body, pending = build_report._gap_read_section()
    assert pending is True


# --------------------------------------------------------------------- F7 (generation guard)
def _setup_report_files(monkeypatch, tmp_path, employer_groups):
    """Lay down an internally-valid CSV + provenance pair, then let the caller
    make employer_groups disagree with the CSV row count."""
    table = pd.DataFrame([
        {"employer": "ACME", "employer_display": "Acme LLC", "filing_count": 2,
         "quarters_present": 1, "quarters": "FY2099Q1", "repeat_sponsor": "no",
         "soc_codes": "15-1255", "soc_titles": "Web and Digital Interface Designers",
         "worksite_states": "TX", "worksite_cities": "Austin",
         "wage_annual_min": 80000, "wage_annual_median": 80000, "wage_annual_max": 80000},
        {"employer": "BETA", "employer_display": "Beta Co", "filing_count": 1,
         "quarters_present": 1, "quarters": "FY2099Q1", "repeat_sponsor": "no",
         "soc_codes": "27-1024", "soc_titles": "Graphic Designers",
         "worksite_states": "NY", "worksite_cities": "New York",
         "wage_annual_min": 70000, "wage_annual_median": 70000, "wage_annual_max": 70000},
    ])
    csv_path = tmp_path / "sponsors_levelI.csv"
    prov_path = tmp_path / "sponsors_levelI.provenance.json"
    table.to_csv(csv_path, index=False, encoding="utf-8", lineterminator="\n")
    provenance = {
        "generated_at_utc": "2099-01-01 00:00 UTC",
        "filters": {"soc_codes": ["15-1255", "27-1024", "27-1021"]},
        "quarters_used": ["FY2099Q1"],
        "funnel": {"rows_total": 10, "rows_certified": 8, "rows_soc_matched": 5, "rows_selected": 3},
        "rows_wage_excluded_from_wage_stats": 0,
        "employer_groups": employer_groups,
    }
    prov_path.write_text(json.dumps(provenance), encoding="utf-8")
    monkeypatch.setattr(build_report, "ensure_dirs", lambda: None)
    # REPO_ROOT must point at tmp too, else the final relative_to() print raises
    # an incidental ValueError and masks the real point (no generation guard).
    monkeypatch.setattr(build_report, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(build_report, "CSV_PATH", csv_path)
    monkeypatch.setattr(build_report, "PROVENANCE_PATH", prov_path)
    monkeypatch.setattr(build_report, "HIRING_NOW_PATH", tmp_path / "hiring_now.csv")
    monkeypatch.setattr(build_report, "GAP_READ_PATH", tmp_path / "gap_read_filled.md")
    monkeypatch.setattr(build_report, "REPORT_PATH", tmp_path / "runway_report.html")


def test_F7_report_refuses_mixed_generation_pair(monkeypatch, tmp_path):
    """F7 (WARN, note): a CSV whose row count disagrees with the provenance's
    employer_groups must stop the build, not render a stale mix."""
    _setup_report_files(monkeypatch, tmp_path, employer_groups=3)  # CSV has 2 rows
    with pytest.raises(RunwayError):
        build_report.build_report()
