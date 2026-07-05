"""Engine unit tests on synthetic in-memory frames.

Covers TEST_SPEC must-index items M1-M7, M9 (engine raise sites), M10.
Every test names the spec item it pins in its function name or docstring; a
test with no anchor would be scope creep (TEST_SPEC §6.1).
"""
from __future__ import annotations

import pytest

from engine import RunwayError
from engine.sponsors import (
    ROLE_SOC,
    build_sponsor_table,
    load_quarters,
    normalize_employer,
    normalize_wage_level,
)

DESIGN = ROLE_SOC["design"]


def build(frame_or_frames, wage_level="I"):
    """Run the engine over one frame or a {label: frame} dict."""
    if isinstance(frame_or_frames, dict):
        quarters = frame_or_frames
    else:
        quarters = {"FY2099Q1": frame_or_frames}
    return build_sponsor_table(DESIGN, wage_level, quarters)


def employers(table):
    return set(table["employer"])


# --------------------------------------------------------------------------- M1
def test_M1_only_exact_certified_passes_status_filter(frame):
    """M1 (dec. #2): only exact, case/whitespace-cleaned `Certified` survives;
    `Certified - Withdrawn`/`Denied`/`Withdrawn` are excluded."""
    f = frame([
        {"EMPLOYER_NAME": "Alpha", "CASE_STATUS": "Certified"},
        {"EMPLOYER_NAME": "Bravo", "CASE_STATUS": "  certified "},   # cleaned -> passes
        {"EMPLOYER_NAME": "Charlie", "CASE_STATUS": "Certified - Withdrawn"},  # excluded
        {"EMPLOYER_NAME": "Delta", "CASE_STATUS": "Denied"},
        {"EMPLOYER_NAME": "Echo", "CASE_STATUS": "Withdrawn"},
    ])
    table, stats = build(f)
    assert stats["rows_certified"] == 2
    assert int(table["filing_count"].sum()) == 2
    assert employers(table) == {"ALPHA", "BRAVO"}
    # The deliberate exclusion that dec. #2 calls out explicitly:
    assert "CHARLIE" not in employers(table)


# ------------------------------------------------------------------------ M2/F6
def test_M2_soc_matched_by_base_code_across_detail_suffixes(frame):
    """M2/F6: SOC match is by base code; O*NET detail suffixes (.00, .01, bare)
    all count; a non-design base code does not."""
    f = frame([
        {"EMPLOYER_NAME": "Base00", "SOC_CODE": "15-1255.00"},
        {"EMPLOYER_NAME": "Detail01", "SOC_CODE": "15-1255.01"},   # video-game designers
        {"EMPLOYER_NAME": "Bare", "SOC_CODE": "15-1255"},
        {"EMPLOYER_NAME": "Graphic", "SOC_CODE": "27-1024.00"},
        {"EMPLOYER_NAME": "Industrial", "SOC_CODE": "27-1021"},
        {"EMPLOYER_NAME": "NonDesign", "SOC_CODE": "15-1252.00"},  # excluded
    ])
    table, stats = build(f)
    assert stats["rows_soc_matched"] == 5
    assert "NONDESIGN" not in employers(table)


def test_F6_detail_suffix_01_is_included(frame):
    """F6 (ratified-in-test-spec, SHOULD): the .01 detail occupation is chosen
    into the shortlist, not an accident of split('.')[0] — pin it explicitly."""
    f = frame([{"EMPLOYER_NAME": "GameStudio", "SOC_CODE": "15-1255.01"}])
    table, _ = build(f)
    assert "GAMESTUDIO" in employers(table)


# --------------------------------------------------------------------------- M3
@pytest.mark.parametrize("value,expected", [
    ("I", "I"), ("II", "II"), ("III", "III"), ("IV", "IV"),
    ("Level I", "I"), ("LEVEL IV", "IV"), ("level ii", "II"),
    ("1", "I"), ("2", "II"), ("3", "III"), ("4", "IV"),
    ("1.0", "I"), ("4.0", "IV"),
    (None, None), ("", None), ("V", None), ("0", None), ("garbage", None),
])
def test_M3_wage_level_spellings_normalize(value, expected):
    """M3: year-to-year wage-level spellings map onto I-IV; unknown -> None."""
    assert normalize_wage_level(value) == expected


def test_M3_all_none_wage_level_quarter_stops(frame):
    """M3: a quarter whose matched rows all have an unrecognized wage level
    selects nothing and stops the run (rather than silently emptying)."""
    f = frame([
        {"EMPLOYER_NAME": "A", "PW_WAGE_LEVEL": "V"},
        {"EMPLOYER_NAME": "B", "PW_WAGE_LEVEL": "unknown"},
    ])
    with pytest.raises(RunwayError, match="prevailing-wage level"):
        build(f)


# --------------------------------------------------------------------------- M4
@pytest.mark.parametrize("unit,from_rate,expected_annual", [
    ("Year", "85000", 85000),
    ("Hour", "40.87", 85010),          # 40.87 * 2080 = 85009.6 -> round
    ("Month", "7000", 84000),          # * 12
    ("Week", "1635", 85020),           # * 52
    ("Year", "$85,000.00", 85000),     # $ and comma parsing
])
def test_M4_annualization_matrix(frame, unit, from_rate, expected_annual):
    """M4 (dec. #8): annual = FROM x {YEAR:1, HOUR:2080, MONTH:12, WEEK:52},
    with $/comma parsing."""
    f = frame([{"EMPLOYER_NAME": "Solo", "WAGE_UNIT_OF_PAY": unit,
                "WAGE_RATE_OF_PAY_FROM": from_rate}])
    table, _ = build(f)
    assert int(table.iloc[0]["wage_annual_median"]) == expected_annual


def test_M4_unparseable_wage_counted_excluded_tallied(frame):
    """M4 (dec. #8): a filing with an out-of-map unit or blank FROM stays in
    every count but contributes no wage stats and is tallied in
    rows_wage_excluded. Dropping it would understate the sponsor."""
    f = frame([
        {"EMPLOYER_NAME": "Mixed", "WAGE_UNIT_OF_PAY": "Year", "WAGE_RATE_OF_PAY_FROM": "80000"},
        {"EMPLOYER_NAME": "Mixed", "WAGE_UNIT_OF_PAY": "Bi-Weekly", "WAGE_RATE_OF_PAY_FROM": "3000"},
        {"EMPLOYER_NAME": "Mixed", "WAGE_UNIT_OF_PAY": "Year", "WAGE_RATE_OF_PAY_FROM": ""},
    ])
    table, stats = build(f)
    row = table.iloc[0]
    assert int(row["filing_count"]) == 3            # all three counted
    assert stats["rows_wage_excluded"] == 2         # two contribute no wage stat
    assert int(row["wage_annual_min"]) == 80000     # stats from the one parseable
    assert int(row["wage_annual_max"]) == 80000


# --------------------------------------------------------------------------- M5
def test_M5_employer_key_conservative(frame):
    """M5 (dec. #9): case/punct/4-suffix normalization only; LLP kept; distinct
    names never merge."""
    assert (normalize_employer("Acme Design LLC")
            == normalize_employer("ACME DESIGN, INC.")
            == normalize_employer("Acme  Design")
            == "ACME DESIGN")
    assert normalize_employer("Deloitte Consulting LLP") == "DELOITTE CONSULTING LLP"
    assert normalize_employer("Acme Design") != normalize_employer("Acme Designs")


@pytest.mark.parametrize("suffix,stripped", [
    ("LLC", True), ("INC", True), ("CORP", True), ("LTD", True),
    ("LLP", False), ("CO", False), ("PLLC", False), ("GROUP", False),
])
def test_M5_only_four_suffixes_stripped(suffix, stripped):
    """M5: exactly LLC/INC/CORP/LTD are stripped; everything else is kept."""
    key = normalize_employer(f"Nimbus {suffix}")
    assert (key == "NIMBUS") is stripped


# --------------------------------------------------------------------------- M6
def test_M6_per_employer_row_is_correct(frame):
    """M6 (dec. #10, amended dec. #21): count, modal display name,
    repeat<=>>=2 distinct FISCAL YEARS, quarters_present, wage min<=median<=max,
    and sort order.

    The repeat vehicle is two DIFFERENT fiscal years (FY2099Q1 + FY2100Q1), not
    two same-FY quarters: DOL's cumulative FYTD files collapse same-FY quarters
    to the latest (supersede, dec. #21 / F1), so within-FY quarter repeat is not
    measurable and repeat is defined across fiscal years."""
    q1 = frame([
        {"EMPLOYER_NAME": "Acme Design LLC", "WAGE_RATE_OF_PAY_FROM": "80000"},
        {"EMPLOYER_NAME": "Acme Design LLC", "WAGE_RATE_OF_PAY_FROM": "100000"},
        {"EMPLOYER_NAME": "ACME DESIGN, INC.", "WAGE_RATE_OF_PAY_FROM": "90000"},
        {"EMPLOYER_NAME": "Solo Co", "WAGE_RATE_OF_PAY_FROM": "70000"},
    ])
    q2 = frame([{"EMPLOYER_NAME": "Acme Design LLC", "WAGE_RATE_OF_PAY_FROM": "95000"}])
    table, _ = build({"FY2099Q1": q1, "FY2100Q1": q2})

    acme = table[table["employer"] == "ACME DESIGN"].iloc[0]
    assert int(acme["filing_count"]) == 4
    assert acme["employer_display"] == "Acme Design LLC"      # modal spelling (3 vs 1)
    assert int(acme["quarters_present"]) == 2
    assert acme["repeat_sponsor"] == "yes"
    assert acme["quarters"] == "FY2099Q1; FY2100Q1"
    assert acme["wage_annual_min"] <= acme["wage_annual_median"] <= acme["wage_annual_max"]

    solo = table[table["employer"] == "SOLO CO"].iloc[0]
    assert int(solo["quarters_present"]) == 1
    assert solo["repeat_sponsor"] == "no"

    # sort: quarters_present desc, filing_count desc, employer asc -> Acme first.
    assert list(table["employer"]) == ["ACME DESIGN", "SOLO CO"]


# --------------------------------------------------------------------------- M7
def test_M7_funnel_monotone_and_partition_and_collapse(frame):
    """M7 (§7): funnel is monotone, Σ filing_count == rows_selected, and
    employer groups never exceed raw spellings."""
    f = frame([
        {"EMPLOYER_NAME": "Acme Design LLC"},
        {"EMPLOYER_NAME": "ACME DESIGN INC"},        # collapses with the above
        {"EMPLOYER_NAME": "Other Studio LLC"},
        {"EMPLOYER_NAME": "Skip Co", "CASE_STATUS": "Denied"},
        {"EMPLOYER_NAME": "Wrong Soc", "SOC_CODE": "15-1252.00"},
        {"EMPLOYER_NAME": "Wrong Level", "PW_WAGE_LEVEL": "III"},
    ])
    table, stats = build(f)
    assert stats["rows_total"] >= stats["rows_certified"] >= stats["rows_soc_matched"] >= stats["rows_selected"]
    assert int(table["filing_count"].sum()) == stats["rows_selected"]
    assert stats["employer_groups"] <= stats["distinct_raw_employers"]


# --------------------------------------------------------------------------- M9
def test_M9_engine_raises_when_no_certified(frame):
    """M9 (dec. #15): no certified rows -> RunwayError, plain English."""
    with pytest.raises(RunwayError, match="Certified"):
        build(frame([{"CASE_STATUS": "Denied"}]))


def test_M9_engine_raises_when_no_soc_match(frame):
    with pytest.raises(RunwayError, match="SOC codes"):
        build(frame([{"SOC_CODE": "15-1252.00"}]))


def test_M9_engine_raises_when_no_rows_at_wage_level(frame):
    with pytest.raises(RunwayError, match="prevailing-wage level"):
        build(frame([{"PW_WAGE_LEVEL": "II"}]))


def test_M9_load_quarters_raises_on_empty_processed_dir(tmp_path):
    with pytest.raises(RunwayError, match="No converted LCA data"):
        load_quarters(tmp_path)


def test_M9_load_quarters_raises_on_missing_columns(tmp_path, frame):
    """M9: a parquet missing an engine column stops with a rebuild instruction."""
    f = frame([{"EMPLOYER_NAME": "A"}]).drop(columns=["PW_WAGE_LEVEL"])
    f.to_parquet(tmp_path / "lca_fy2099q1.parquet", index=False)
    with pytest.raises(RunwayError, match="missing column"):
        load_quarters(tmp_path)


def test_M9_messages_are_plain_english_not_blank(frame):
    """M9: every raised message leads with a human sentence (not an error code)."""
    with pytest.raises(RunwayError) as exc:
        build(frame([{"CASE_STATUS": "Denied"}]))
    first_line = str(exc.value).splitlines()[0]
    assert first_line and first_line[0].isupper() and first_line.endswith(".")


# -------------------------------------------------------------------------- M10
def _write_quarter(processed_dir, label, frame_builder):
    yyyy, q = label[2:6], label[-1]
    path = processed_dir / f"lca_fy{yyyy}q{q}.parquet"
    frame_builder([{"EMPLOYER_NAME": f"Emp {label}"}]).to_parquet(path, index=False)
    return path


def test_M10_quarters_flag_is_assertion_not_selector(tmp_path, frame):
    """M10 (dec. #11): --quarters asserts presence; extra quarters are always
    used, and a requested-but-missing quarter stops the run."""
    _write_quarter(tmp_path, "FY2099Q1", frame)
    _write_quarter(tmp_path, "FY2099Q2", frame)

    # Requesting only Q1 still loads the extra Q2 (assertion, never a selector).
    loaded = load_quarters(tmp_path, requested=["FY2099Q1"])
    assert set(loaded) == {"FY2099Q1", "FY2099Q2"}

    # No request -> every converted quarter present.
    assert set(load_quarters(tmp_path)) == {"FY2099Q1", "FY2099Q2"}

    # Loose spelling still matches (case/space-insensitive).
    assert set(load_quarters(tmp_path, requested=["fy2099 q1"])) == {"FY2099Q1", "FY2099Q2"}


def test_M10_missing_requested_quarter_stops(tmp_path, frame):
    """M10: a requested quarter with no converted data stops, naming it."""
    _write_quarter(tmp_path, "FY2099Q1", frame)
    with pytest.raises(RunwayError, match="FY2099Q3"):
        load_quarters(tmp_path, requested=["FY2099Q3"])
