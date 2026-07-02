"""Runway — Layer 1 verification (T2).

The "verification cell": a failed check raises and stops the run, so a wrong
file (e.g. PERM instead of LCA), an empty post-filter result, or a normalization
regression can never silently produce a bogus shortlist.

Golden checks are reanchored to the kill-test's *real* numbers (FY2025 Q4):
  - top single-quarter sponsor iGavel (7 Level-I design filings) reappears,
  - a suffixed/multi-spelling employer collapses to one normalized row.
"""

from __future__ import annotations

import pandas as pd

from .sponsors import REQUIRED_COLUMNS, normalize_employer


class VerificationError(AssertionError):
    """A Layer 1 verification check failed; the shortlist is not trustworthy."""


def _check(ok: bool, msg: str) -> str:
    if not ok:
        raise VerificationError(msg)
    return f"PASS — {msg}"


def verify_normalization_unit() -> list[str]:
    """Data-independent: normalize_employer collapses spellings as intended."""
    out = []
    cases = {
        "The Deloitte Consulting, LLP.": "DELOITTE CONSULTING",
        "Deloitte Consulting LLP": "DELOITTE CONSULTING",
        "Amazon.com Services LLC": "AMAZON COM SERVICES",
        "AMAZON.COM SERVICES, INC.": "AMAZON COM SERVICES",
    }
    for raw, expected in cases.items():
        got = normalize_employer(raw)
        out.append(_check(got == expected, f"normalize({raw!r}) == {expected!r} (got {got!r})"))
    return out


def verify_columns(rows: pd.DataFrame) -> str:
    """Column-present assert — catches a wrong/PERM file before trusting output."""
    missing = [c for c in REQUIRED_COLUMNS if c not in rows.columns]
    return _check(not missing, f"all required columns present (missing: {missing})")


def verify_nonempty(table: pd.DataFrame) -> str:
    """Non-empty-after-filter assert — the door is not closed / filter not broken."""
    return _check(len(table) > 0, f"sponsor table non-empty after filtering ({len(table)} employers)")


def verify_count_consistency(table: pd.DataFrame, rows: pd.DataFrame) -> str:
    """Sum of per-employer filing_count == number of selected certified rows."""
    total = int(table["filing_count"].sum())
    n_rows = len(rows)
    return _check(total == n_rows, f"filing_count sums to selected rows ({total} == {n_rows})")


def verify_collapse(rows: pd.DataFrame, table: pd.DataFrame) -> str:
    """A normalized employer with >1 raw spelling collapses to a single row.

    Confirms the group-by actually merged multi-entity / suffix variants rather
    than leaving them as separate rows.
    """
    raw_per_norm = rows.groupby("EMP_NORM")["EMPLOYER_NAME"].nunique()
    multi = raw_per_norm[raw_per_norm > 1]
    if multi.empty:
        # No multi-spelling employer this run; assert grouping still reduced rows.
        return _check(
            len(table) <= len(rows),
            f"grouping reduced {len(rows)} rows to {len(table)} employers",
        )
    emp = multi.index[0]
    n_spellings = int(multi.iloc[0])
    n_table_rows = int((table["employer"] == emp).sum())
    return _check(
        n_table_rows == 1,
        f"multi-spelling employer {emp!r} ({n_spellings} raw spellings) "
        f"collapsed to {n_table_rows} row",
    )


def verify_golden_killtest(
    rows: pd.DataFrame, table: pd.DataFrame, killtest_top: str = "IGAVEL", anchor_quarter: str = "FY2025Q4"
) -> str:
    """The kill-test's top single-quarter sponsor reappears in the full table.

    This golden value (IGAVEL, 7 Level-I design filings) is specific to
    FY2025 Q4. It only means anything when that quarter is in the run — on any
    other data it would fire a false failure — so it is *skipped* (not failed)
    when the anchor quarter isn't loaded.
    """
    quarters = set(rows["QUARTER"].unique()) if "QUARTER" in rows.columns else set()
    if anchor_quarter not in quarters:
        return f"SKIP — golden kill-test anchored to {anchor_quarter} (not in this run)"
    present = killtest_top in set(table["employer"])
    return _check(present, f"kill-test top sponsor {killtest_top!r} present in shortlist")


def run_all(rows: pd.DataFrame, table: pd.DataFrame, killtest_top: str = "IGAVEL") -> list[str]:
    """Run every check; raise on the first failure, else return the PASS log."""
    results: list[str] = []
    results += verify_normalization_unit()
    results.append(verify_columns(rows))
    results.append(verify_nonempty(table))
    results.append(verify_count_consistency(table, rows))
    results.append(verify_collapse(rows, table))
    results.append(verify_golden_killtest(rows, table, killtest_top))
    return results
