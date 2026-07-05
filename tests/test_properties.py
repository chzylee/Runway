"""Property tests (hypothesis, dev-only per dec. #17 / TEST_SPEC §3).

Falsifiable invariants I1-I8. I8 was committed as xfail(strict) - the
property-level statement of the cumulative-overlap double-count (F1) that the
engine violated; stage 6 (finish-build) built the same-FY supersede mechanism
(dec. #21) and removed the marker. It now asserts green.
"""
from __future__ import annotations

import string

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from engine.sponsors import (
    CORPORATE_SUFFIXES,
    ROLE_SOC,
    build_sponsor_table,
    normalize_employer,
    normalize_wage_level,
)
from conftest import make_frame

DESIGN = ROLE_SOC["design"]
_ALNUM = string.ascii_letters + string.digits
_ANY = st.text(min_size=0, max_size=40)


# --------------------------------------------------------------------------- I1
@given(_ANY)
def test_I1_normalize_employer_idempotent(s):
    """I1 (M5): f(f(x)) == f(x) for any string."""
    once = normalize_employer(s)
    assert normalize_employer(once) == once


# --------------------------------------------------------------------------- I2
@given(st.text(alphabet=string.ascii_uppercase + string.digits, min_size=1, max_size=6)
       .filter(lambda t: t not in CORPORATE_SUFFIXES))
def test_I2_distinguishing_non_suffix_token_prevents_merge(extra):
    """I2 (M5, dec. #9): two names differing by a non-suffix token never merge —
    the conservative direction (under-merge over over-merge)."""
    assert normalize_employer(f"ACME {extra}") != normalize_employer("ACME")


# --------------------------------------------------------------------------- I3
@given(_ANY)
def test_I3_normalize_employer_never_raises_returns_str(s):
    """I3 (J7): normalize_employer never raises and always returns a string."""
    result = normalize_employer(s)
    assert isinstance(result, str)


@given(st.text(alphabet="  ,.-/&()'\"!@#$%", min_size=0, max_size=20))
def test_I3_punctuation_only_yields_empty_key(s):
    """I3 (J7): empty/punctuation-only input collapses to the empty key."""
    assert normalize_employer(s) == ""


# --------------------------------------------------------------------------- I4
@given(st.one_of(_ANY, st.integers(), st.floats(allow_nan=True), st.none()))
def test_I4_normalize_wage_level_is_total(value):
    """I4 (M3): any input maps into {I, II, III, IV, None} and never raises."""
    assert normalize_wage_level(value) in {"I", "II", "III", "IV", None}


# ----------------------------------------------------------------- frame strategy
_KINDS = ["ok", "denied", "wrong_soc", "wrong_level"]
_UNITS = ["Year", "Hour", "Month", "Week", "Bi-Weekly", ""]
_WAGES = ["85000", "40.50", "$70,000", "", "not-a-number", "0"]


@st.composite
def _row(draw):
    kind = draw(st.sampled_from(_KINDS))
    r = {
        "EMPLOYER_NAME": draw(st.text(alphabet=_ALNUM + " ,.-", min_size=0, max_size=10)),
        "WAGE_UNIT_OF_PAY": draw(st.sampled_from(_UNITS)),
        "WAGE_RATE_OF_PAY_FROM": draw(st.sampled_from(_WAGES)),
    }
    if kind == "denied":
        r["CASE_STATUS"] = "Denied"
    elif kind == "wrong_soc":
        r["SOC_CODE"] = "15-1252.00"
    elif kind == "wrong_level":
        r["PW_WAGE_LEVEL"] = "III"
    return r


@st.composite
def _selectable_frame(draw):
    # Always include one guaranteed-selected row so the engine never hits the
    # empty-selection RunwayError; the property is about the aggregation, not
    # the guard (that is V1).
    rows = [{"EMPLOYER_NAME": "Anchor Studio LLC", "WAGE_RATE_OF_PAY_FROM": "90000"}]
    rows += draw(st.lists(_row(), min_size=0, max_size=8))
    return make_frame(rows)


# ------------------------------------------------------------------------ I5/I6/I7
@settings(max_examples=60, deadline=None)
@given(_selectable_frame())
def test_I5_I6_I7_aggregation_invariants(f):
    """I5 (partition: Σ filing_count == rows_selected), I6 (min<=median<=max
    where wage stats exist), I7 (funnel monotone)."""
    table, stats = build_sponsor_table(DESIGN, "I", {"FY2099Q1": f})

    # I7 — monotone funnel.
    assert stats["rows_total"] >= stats["rows_certified"] >= stats["rows_soc_matched"] >= stats["rows_selected"]
    # I5 — the aggregation partitions the selected filings exactly.
    assert int(table["filing_count"].sum()) == stats["rows_selected"]
    assert stats["employer_groups"] <= stats["distinct_raw_employers"]
    # I6 — wage ordering wherever stats exist.
    waged = table.dropna(subset=["wage_annual_min", "wage_annual_median", "wage_annual_max"])
    for _, r in waged.iterrows():
        assert r["wage_annual_min"] <= r["wage_annual_median"] <= r["wage_annual_max"]


# --------------------------------------------------------------------------- I8
@settings(max_examples=25, deadline=None)
@given(employer=st.text(alphabet=_ALNUM + " ", min_size=1, max_size=10),
       wage=st.sampled_from(["85000", "60000", "120000"]))
def test_I8_no_filing_counted_twice_across_cumulative_quarters(employer, wage):
    """I8 (WARN): one filing present in two cumulative quarter files must count
    once, not twice, and must not fabricate a repeat_sponsor signal."""
    row = {"EMPLOYER_NAME": employer, "WAGE_RATE_OF_PAY_FROM": wage}
    q_earlier = make_frame([row])
    q_later = make_frame([row])  # cumulative file re-lists the same filing
    table, _ = build_sponsor_table(DESIGN, "I",
                                   {"FY2030Q1": q_earlier, "FY2030Q2": q_later})
    assert int(table.iloc[0]["filing_count"]) == 1
    assert table.iloc[0]["repeat_sponsor"] == "no"
