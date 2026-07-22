"""v1 Increment 1 — the web/data/ emit (Design Doc §4.2 closed schema, §4.3 guard).

Runs the REAL convert -> shortlist -> emit path against the committed synthetic
fixture (tests/dol_xlsx.py + its EXPECTED oracle) via the emit_env fixture, then
asserts the closed design.json schema, JSON-null wage handling (the v0 F5 successor),
the same-generation guard firing (v0 F7/§8 successor), provenance/CSV parity, and
unicode/UTF-8. The fixture is the ONLY place the null-wage path is exercised — the
real FY2025Q4 data has 0 wage-excluded filings.
"""
from __future__ import annotations

import json

import pandas as pd
import pytest

import build_shortlist
import dol_xlsx
from engine import RunwayError
from _util import CAVEATS

FIXTURE = dol_xlsx.FIXTURE_PATH
EXPECTED = dol_xlsx.EXPECTED

# The §4.2 closed top-level key set + employer column order, retyped from the Design
# Doc as an independent oracle (not read back from the code under test).
DESIGN_JSON_KEYS = {
    "role", "generated_at_utc", "source", "filters", "quarters_used",
    "quarters_superseded", "funnel", "employer_groups",
    "rows_wage_excluded_from_wage_stats", "patterns", "caveats", "employers",
}
EMPLOYER_COLUMNS = [
    "employer", "employer_display", "filing_count", "quarters_present", "quarters",
    "repeat_sponsor", "soc_codes", "soc_titles", "worksite_states", "worksite_cities",
    "wage_annual_min", "wage_annual_median", "wage_annual_max",
]


@pytest.fixture
def emitted(emit_env):
    """Place the fixture, run convert -> shortlist -> emit, return (env, design.json)."""
    emit_env.place_fixture(FIXTURE)
    emit_env.run()
    design = json.loads(emit_env.json.read_text(encoding="utf-8"))
    return emit_env, design


# ---------------------------------------------------------------- closed schema
def test_design_json_is_the_closed_schema(emitted):
    """§4.2: design.json top-level keys are EXACTLY the closed set — a field not in the
    schema is a fork to decision-log, never a silent add."""
    _, design = emitted
    assert set(design.keys()) == DESIGN_JSON_KEYS


def test_employers_columns_exact_and_ordered(emitted):
    """§4.2: employers[] carry exactly the v0 CSV columns, in order."""
    _, design = emitted
    assert design["employers"], "expected a non-empty shortlist"
    for row in design["employers"]:
        assert list(row.keys()) == EMPLOYER_COLUMNS


def test_filters_shape_json_vs_provenance(emitted):
    """§4.2: design.json.filters = {case_status, soc_codes, pw_wage_level} — role is
    top-level, NOT in filters; the provenance object keeps the full v0 filters (w/ role)."""
    env, design = emitted
    assert design["filters"] == {
        "case_status": "Certified",
        "soc_codes": ["15-1255", "27-1024", "27-1021"],
        "pw_wage_level": "I",
    }
    assert design["role"] == "design"
    prov = json.loads(env.provenance.read_text(encoding="utf-8"))
    assert prov["filters"]["role"] == "design"


def test_caveats_verbatim_from_engine(emitted):
    """§7: design.json.caveats are engine/_util.CAVEATS verbatim (single source of truth)."""
    _, design = emitted
    assert design["caveats"] == CAVEATS
    assert len(design["caveats"]) == 5


# ------------------------------------------------------------ gotcha: null wages
def test_null_wage_is_json_null_never_nan(emitted):
    """§4.2 (v0 F5 successor): an all-wage-excluded employer (Blank Fields Co — its one
    filing is Bi-Weekly, outside the annualization map) has null wage stats emitted as
    JSON null, and the literal "nan"/NaN never appears anywhere in design.json."""
    env, design = emitted
    by_display = {e["employer_display"]: e for e in design["employers"]}
    blank = by_display["Blank Fields Co"]
    assert blank["wage_annual_min"] is None
    assert blank["wage_annual_median"] is None
    assert blank["wage_annual_max"] is None
    raw = env.json.read_text(encoding="utf-8")
    assert "nan" not in raw.lower()
    assert "NaN" not in raw          # json.dumps(allow_nan=True) would leak this


def test_numbers_are_json_numbers(emitted):
    """§4.2: counts and present wages are JSON numbers (ints), never strings/floats."""
    _, design = emitted
    assert isinstance(design["employer_groups"], int)
    assert isinstance(design["funnel"]["rows_selected"], int)
    for e in design["employers"]:
        assert isinstance(e["filing_count"], int)
        assert isinstance(e["quarters_present"], int)
        for column in ("wage_annual_min", "wage_annual_median", "wage_annual_max"):
            assert e[column] is None or isinstance(e[column], int)


def test_patterns_block_matches_expected(emitted):
    """dec. #44: design.json.patterns equals the hand-derived oracle exactly —
    basis, floor-gated recurring tokens, verbatim distinct titles, the O*NET split
    (suffix preserved), placement model, and floor-gated industry sectors."""
    _, design = emitted
    assert design["patterns"] == EXPECTED["patterns"]


def test_patterns_floor_and_denominator_hold(emitted):
    """dec. #44: no recurring token or industry sector is emitted below the employer
    support floor, and the pattern basis employer count equals employer_groups."""
    _, design = emitted
    patterns = design["patterns"]
    floor = patterns["basis"]["min_support_employers"]
    assert patterns["basis"]["employers"] == design["employer_groups"]
    for entry in patterns["job_titles"]["recurring_tokens"] + patterns["industry_naics2"]:
        assert entry["employers"] >= floor
        assert entry["employers"] <= patterns["basis"]["employers"]
    # distinct_titles is verbatim evidence: NOT floor-gated, so a 1-employer title survives.
    assert any(t["employers"] < floor for t in patterns["job_titles"]["distinct_titles"])


def test_funnel_and_counts_match_expected(emitted):
    """The emitted funnel + per-employer wage stats equal the hand-derived oracle."""
    _, design = emitted
    assert design["employer_groups"] == EXPECTED["employer_groups"]
    assert design["funnel"]["rows_selected"] == EXPECTED["rows_selected"]
    assert design["funnel"]["rows_total"] == EXPECTED["rows_total"]
    assert design["rows_wage_excluded_from_wage_stats"] == EXPECTED["rows_wage_excluded"]
    by_display = {e["employer_display"]: e for e in design["employers"]}
    for display, (count, wmin, wmed, wmax) in EXPECTED["employers"].items():
        e = by_display[display]
        assert e["filing_count"] == count
        assert (e["wage_annual_min"], e["wage_annual_median"], e["wage_annual_max"]) == (wmin, wmed, wmax)


# ----------------------------------------------------------- unicode / parity
def test_unicode_employer_roundtrips_json_and_csv(emitted):
    """dec.#14: a non-ASCII employer (Café Studio LLC) survives into both artifacts."""
    env, design = emitted
    displays = {e["employer_display"] for e in design["employers"]}
    assert "Café Studio LLC" in displays
    assert "Café Studio LLC" in env.csv.read_text(encoding="utf-8")


def test_csv_has_v0_columns(emitted):
    """design.csv keeps the v0 public-shortlist columns (the download artifact)."""
    env, _ = emitted
    csv = pd.read_csv(env.csv, encoding="utf-8")
    assert list(csv.columns) == EMPLOYER_COLUMNS


def test_provenance_is_full_v0_object(emitted):
    """§4.2: design.provenance.json is the FULL v0 provenance object (audit token)."""
    env, _ = emitted
    prov = json.loads(env.provenance.read_text(encoding="utf-8"))
    for key in ("generated_at_utc", "source", "filters", "quarters_used",
                "quarters_superseded", "rows_per_quarter", "funnel", "employer_groups",
                "distinct_raw_employer_spellings", "rows_wage_excluded_from_wage_stats",
                "case_statuses_seen", "wage_levels_seen", "wage_units_seen", "patterns", "caveats"):
        assert key in prov, f"provenance missing {key}"


# ------------------------------------------------------------ gotcha: the guard
def test_same_generation_guard_fires(emit_env, monkeypatch):
    """§4.3 (v0 F7/§8 successor): if the three employer counts disagree, the emit must
    REFUSE to write a stale mix. Fault-injected (the counts agree by construction), so
    this pins the guard against the "a check that can't fire" failure mode."""
    real = build_shortlist.build_sponsor_table

    def corrupt(soc_codes, wage_level, quarters):
        table, stats = real(soc_codes, wage_level, quarters)
        stats = dict(stats)
        stats["employer_groups"] = stats["employer_groups"] - 1   # provenance disagrees w/ rows
        # Keep the pattern basis consistent with the corrupted count so the engine-level
        # check_patterns_consistent passes and the disagreement reaches the EMIT guard
        # (which this test pins): the table rows (uncorrupted) will then out-vote it.
        stats["patterns"] = {**stats["patterns"],
                             "basis": {**stats["patterns"]["basis"],
                                       "employers": stats["employer_groups"]}}
        return table, stats

    monkeypatch.setattr(build_shortlist, "build_sponsor_table", corrupt)
    emit_env.place_fixture(FIXTURE)
    with pytest.raises(RunwayError) as excinfo:
        emit_env.run()
    assert "same-generation" in str(excinfo.value).lower()
    assert not emit_env.json.exists()          # nothing written when the guard fires


def test_missing_requested_quarter_stops_before_emit(emit_env):
    """§9 (v0 dec.#11): --quarters asserts; a requested quarter with no data stops with a
    RunwayError naming it, before any artifact is written."""
    emit_env.place_fixture(FIXTURE)            # only FY2099Q1 present
    with pytest.raises(RunwayError) as excinfo:
        emit_env.run(requested_quarters=["FY2025Q4"])
    assert "FY2025Q4" in str(excinfo.value)
    assert not emit_env.json.exists()
