"""In-pipeline verification: every check passes, skips, or stops the run.

A failed check raises RunwayError so a bad run never quietly produces
artifacts. Checks return CheckResult(status "PASS" or "SKIP") so the scripts
can print what was verified.
"""
from __future__ import annotations

from collections import namedtuple

from engine import RunwayError
from engine.sponsors import (
    REQUIRED_COLUMNS,
    ROLE_SOC,
    build_sponsor_table,
    normalize_employer,
)

CheckResult = namedtuple("CheckResult", ["name", "status", "detail"])

# Anchor for the golden check, pinned from the verified manual run of
# 2026-07-01 (see docs/decision_log.md): in FY2025Q4, the top Level-I design
# sponsor by filing count is iGavel, Inc. (7 filings). The check SKIPS when
# that quarter isn't loaded, so it never fires a false failure on other data.
GOLDEN = {
    "quarter": "FY2025Q4",
    "role": "design",
    "wage_level": "I",
    "top_employer": "IGAVEL",
}


def check_required_columns(columns, source: str) -> CheckResult:
    """Catches a wrong file early - a PERM disclosure has different columns."""
    present = set(columns)
    missing = [c for c in REQUIRED_COLUMNS if c not in present]
    if missing:
        raise RunwayError(
            f"{source} is missing required column(s): {', '.join(missing)}.\n"
            "This looks like the wrong file - a PERM disclosure instead of an LCA one?\n"
            "Download the LCA Programs file named LCA_Disclosure_Data_FY<YYYY>_Q<N>.xlsx\n"
            "(not PERM_...) from the DOL disclosure-data page linked in README.md."
        )
    return CheckResult(
        "required-columns", "PASS",
        f"all {len(REQUIRED_COLUMNS)} required columns present in {source}",
    )


def check_nonempty(table, stats) -> CheckResult:
    if stats["rows_selected"] == 0 or len(table) == 0:
        raise RunwayError(
            "The filters selected no rows, so there is nothing to report.\n"
            f"Funnel: {stats['rows_total']} rows -> {stats['rows_certified']} certified "
            f"-> {stats['rows_soc_matched']} in role SOC codes -> {stats['rows_selected']} at the wage level."
        )
    return CheckResult(
        "non-empty-result", "PASS",
        f"{stats['rows_selected']} selected filings across {stats['employer_groups']} employers",
    )


def check_filing_count_sum(table, stats) -> CheckResult:
    total = int(table["filing_count"].sum())
    if total != stats["rows_selected"]:
        raise RunwayError(
            f"filing_count sums to {total} but {stats['rows_selected']} rows were selected -\n"
            "the aggregation dropped or duplicated filings. Do not trust this run."
        )
    return CheckResult(
        "filing-count-sum", "PASS",
        f"filing_count sums to the {total} selected rows",
    )


def check_employer_collapse(table, stats) -> CheckResult:
    """A multi-spelling employer must collapse to one row."""
    spellings = ["Acme Design LLC", "ACME DESIGN, INC.", "Acme  Design"]
    keys = {normalize_employer(s) for s in spellings}
    if len(keys) != 1:
        raise RunwayError(
            f"Employer normalization is broken: {spellings} produced keys {sorted(keys)} "
            "instead of one shared key."
        )
    raw = stats["distinct_raw_employers"]
    grouped = stats["employer_groups"]
    if grouped > raw:
        raise RunwayError(
            f"Grouping produced MORE employers ({grouped}) than raw spellings ({raw}) - "
            "the group key is unstable. Do not trust this run."
        )
    if grouped < raw:
        detail = f"{raw} raw spellings collapsed into {grouped} employers"
    else:
        detail = ("no multi-spelling employers in this data; "
                  "normalization mechanism verified on synthetic names")
    return CheckResult("employer-collapse", "PASS", detail)


def check_patterns_consistent(table, stats) -> CheckResult:
    """The title-shortlist patterns (dec. #44) are internally consistent with the
    shortlist they summarize: the pattern basis employer count equals the number
    of employer groups, no bucket claims more employers than the basis, and every
    floor-gated entry actually clears the support floor. A pattern that overstated
    its support would corrupt the very confidence the block exists to give."""
    patterns = stats.get("patterns")
    if not patterns:
        raise RunwayError(
            "Stats carry no patterns block, but the emit expects one (dec. #44).\n"
            "compute_patterns() did not run - do not trust this run."
        )
    basis = patterns["basis"]
    if basis["employers"] != stats["employer_groups"]:
        raise RunwayError(
            f"Pattern basis employers ({basis['employers']}) != employer_groups "
            f"({stats['employer_groups']}). Patterns and shortlist disagree on the "
            "denominator - do not trust this run."
        )
    floor = basis["min_support_employers"]
    floored = list(patterns["job_titles"]["recurring_tokens"]) + list(patterns["industry_naics2"])
    for entry in floored:
        if entry["employers"] < floor:
            raise RunwayError(
                f"A floor-gated pattern entry ({entry}) is below the support floor "
                f"({floor} employers) - the gate leaked. Do not trust this run."
            )
        if entry["employers"] > basis["employers"]:
            raise RunwayError(
                f"A pattern entry ({entry}) claims more employers than the basis "
                f"({basis['employers']}) - counting is broken. Do not trust this run."
            )
    return CheckResult(
        "patterns-consistent", "PASS",
        f"{len(patterns['job_titles']['recurring_tokens'])} recurring token(s), "
        f"{len(patterns['industry_naics2'])} industry sector(s) above the "
        f"{floor}-employer floor; basis {basis['employers']} employers",
    )


def check_golden_top_employer(quarters) -> CheckResult:
    """Recompute the pinned quarter from its own rows and compare the top
    employer against the known answer."""
    if GOLDEN["quarter"] not in quarters:
        return CheckResult(
            "golden-top-employer", "SKIP",
            f"{GOLDEN['quarter']} not loaded; nothing to compare against",
        )
    golden_table, _ = build_sponsor_table(
        ROLE_SOC[GOLDEN["role"]],
        GOLDEN["wage_level"],
        {GOLDEN["quarter"]: quarters[GOLDEN["quarter"]]},
    )
    top = golden_table.iloc[0]
    if top["employer"] != GOLDEN["top_employer"]:
        raise RunwayError(
            f"Golden check failed on {GOLDEN['quarter']}: expected top employer "
            f"{GOLDEN['top_employer']}, got {top['employer']} ({int(top['filing_count'])} filings).\n"
            "Filtering or normalization behavior changed - investigate before trusting this run."
        )
    return CheckResult(
        "golden-top-employer", "PASS",
        f"{GOLDEN['quarter']} top employer is {GOLDEN['top_employer']} "
        f"({int(top['filing_count'])} filings), as pinned",
    )


def run_all(table, stats, quarters) -> list[CheckResult]:
    """Run every table-level check; raises RunwayError on the first failure."""
    return [
        check_nonempty(table, stats),
        check_filing_count_sum(table, stats),
        check_employer_collapse(table, stats),
        check_patterns_consistent(table, stats),
        check_golden_top_employer(quarters),
    ]
