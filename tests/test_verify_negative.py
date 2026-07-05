"""Trust-check negative tests: every verify.py guard must demonstrably FIRE.

TEST_SPEC §8.1 / V1-V4: a check that cannot fail manufactures confidence on
every run. Each check is shown to RAISE on corrupted input; a passing case is
included alongside so the raise is proven to discriminate (not vacuous).
M11 (golden check PASS/SKIP) lives here too since it shares the fixtures.
"""
from __future__ import annotations

import pandas as pd
import pytest

from engine import RunwayError
from engine.verify import (
    check_employer_collapse,
    check_filing_count_sum,
    check_golden_top_employer,
    check_nonempty,
)

# --------------------------------------------------------------------------- V1
def test_V1_check_nonempty_fires_on_empty_selection():
    """V1: check_nonempty must raise when the filters selected no rows."""
    empty_stats = {"rows_selected": 0, "rows_total": 100, "rows_certified": 5,
                   "rows_soc_matched": 0}
    with pytest.raises(RunwayError, match="nothing to report"):
        check_nonempty(pd.DataFrame(), empty_stats)


def test_V1_check_nonempty_passes_on_real_selection():
    ok_stats = {"rows_selected": 3, "employer_groups": 2}
    result = check_nonempty(pd.DataFrame([{"filing_count": 2}, {"filing_count": 1}]), ok_stats)
    assert result.status == "PASS"


# --------------------------------------------------------------------------- V2
def test_V2_check_filing_count_sum_fires_on_drop_or_duplicate():
    """V2: when filing_count no longer sums to rows_selected (a dropped and a
    duplicated filing), the aggregation is untrustworthy and must stop."""
    table = pd.DataFrame([{"filing_count": 3}, {"filing_count": 3}])  # sums to 6
    with pytest.raises(RunwayError, match="dropped or duplicated"):
        check_filing_count_sum(table, {"rows_selected": 5})


def test_V2_check_filing_count_sum_passes_when_balanced():
    table = pd.DataFrame([{"filing_count": 3}, {"filing_count": 3}])
    assert check_filing_count_sum(table, {"rows_selected": 6}).status == "PASS"


# --------------------------------------------------------------------------- V3
def test_V3_check_employer_collapse_fires_when_groups_exceed_raw():
    """V3: more employer groups than raw spellings means the group key is
    unstable — impossible for a correct partition, so it must stop."""
    with pytest.raises(RunwayError, match="MORE employers"):
        check_employer_collapse(pd.DataFrame(),
                                {"distinct_raw_employers": 3, "employer_groups": 5})


def test_V3_check_employer_collapse_passes_when_collapsing():
    result = check_employer_collapse(pd.DataFrame(),
                                     {"distinct_raw_employers": 5, "employer_groups": 4})
    assert result.status == "PASS"


# ------------------------------------------------------------------------ V4/M11
def _fy2025q4(frame, rows):
    return {"FY2025Q4": frame(rows)}


def test_V4_golden_check_fires_when_igavel_not_top(frame):
    """V4 (dec. #12): recomputing FY2025Q4 and finding a different top employer
    than the pinned iGavel means filter/normalization drift — must stop."""
    quarters = _fy2025q4(frame, [
        {"EMPLOYER_NAME": "Bigco LLC"},
        {"EMPLOYER_NAME": "Bigco LLC"},
        {"EMPLOYER_NAME": "iGavel, Inc."},
    ])
    with pytest.raises(RunwayError, match="Golden check failed"):
        check_golden_top_employer(quarters)


def test_M11_golden_check_passes_when_igavel_is_top(frame):
    """M11: FY2025Q4 with iGavel on top passes the golden check."""
    quarters = _fy2025q4(frame, [
        {"EMPLOYER_NAME": "iGavel, Inc."},
        {"EMPLOYER_NAME": "iGavel, Inc."},
        {"EMPLOYER_NAME": "Bigco LLC"},
    ])
    result = check_golden_top_employer(quarters)
    assert result.status == "PASS"
    assert "IGAVEL" in result.detail


def test_M11_golden_check_skips_when_quarter_absent(frame):
    """M11 (dec. #12): when FY2025Q4 isn't loaded the check SKIPS — it never
    fires a false failure on other data."""
    quarters = {"FY2099Q1": frame([{"EMPLOYER_NAME": "Whoever LLC"}])}
    result = check_golden_top_employer(quarters)
    assert result.status == "SKIP"
