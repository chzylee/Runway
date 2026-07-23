"""Discover which SOC codes real DOL filings use for a job-title pattern -
the repeatable first step for adding a role to engine.sponsors.ROLE_SOC.

    python scripts/discover_role.py "software engineer"
    python scripts/discover_role.py "consultant" --level I --min-employers 3

Prints, for every certified filing whose JOB_TITLE matches the pattern, a
table of SOC codes ranked by DISTINCT EMPLOYER count - the same denominator
the engine's title-shortlist patterns use (PATTERN_MIN_SUPPORT), so a role's
SOC list is chosen from what employers actually filed under that title, not
memory. --level restricts to one PW_WAGE_LEVEL (e.g. "I", what the shortlist
itself filters to), since a title can be dominated by a different SOC code at
entry level than overall.

This script only prints. Deciding what belongs in ROLE_SOC, and writing the
decision log entry, stays a human judgment call - see dec. #3 (title-keyword
matching was rejected for the shortlist filter itself; this is a research aid
for choosing SOC codes, not a new filter path) and dec. #45+ for worked
examples of reading this table.
"""
import argparse
import re
from collections import defaultdict

import pandas as pd

import _util
from _util import DATA_PROCESSED, run_cli

from engine.sponsors import (
    load_quarters,
    normalize_employer,
    normalize_soc,
    normalize_wage_level,
    supersede_cumulative_quarters,
)


def discover(pattern, *, regex=False, level=None, min_employers=1):
    quarters = load_quarters(DATA_PROCESSED)
    quarters, _superseded = supersede_cumulative_quarters(quarters)
    rows = pd.concat(list(quarters.values()), ignore_index=True)

    status = rows["CASE_STATUS"].fillna("").astype(str).str.strip().str.upper()
    certified = rows[status == "CERTIFIED"]

    needle = pattern if regex else re.escape(pattern)
    titles = certified["JOB_TITLE"].fillna("").astype(str)
    matched = certified[titles.str.contains(needle, case=False, na=False, regex=True)]

    if level:
        levels = matched["PW_WAGE_LEVEL"].map(normalize_wage_level)
        matched = matched[levels == level.strip().upper()]

    if matched.empty:
        return []

    soc_codes = matched["SOC_CODE"].map(normalize_soc)
    employer_keys = matched["EMPLOYER_NAME"].map(normalize_employer)
    soc_titles = matched["SOC_TITLE"].fillna("").astype(str)

    employers_by_soc = defaultdict(set)
    filings_by_soc = defaultdict(int)
    title_votes_by_soc = defaultdict(lambda: defaultdict(int))
    for code, emp_key, soc_title in zip(soc_codes, employer_keys, soc_titles):
        if not code:
            continue
        employers_by_soc[code].add(emp_key)
        filings_by_soc[code] += 1
        soc_title = soc_title.strip()
        if soc_title:
            title_votes_by_soc[code][soc_title] += 1

    results = []
    for code, employers in employers_by_soc.items():
        if len(employers) < min_employers:
            continue
        votes = title_votes_by_soc[code]
        best_title = max(votes, key=votes.get) if votes else ""
        results.append({
            "soc_code": code,
            "soc_title": best_title,
            "employers": len(employers),
            "filings": filings_by_soc[code],
        })
    results.sort(key=lambda r: (-r["employers"], -r["filings"], r["soc_code"]))
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Show which SOC codes real DOL filings use for a job-title pattern - "
                     "the research step before adding a role to engine.sponsors.ROLE_SOC."
    )
    parser.add_argument("pattern", help='title substring to search, e.g. "software engineer"')
    parser.add_argument("--regex", action="store_true",
                         help="treat PATTERN as a regex instead of a plain substring")
    parser.add_argument("--level", help='restrict to one PW_WAGE_LEVEL, e.g. "I"')
    parser.add_argument("--min-employers", type=int, default=1,
                         help="hide SOC codes backed by fewer than this many distinct "
                              "employers (default 1)")
    args = parser.parse_args()

    results = discover(
        args.pattern, regex=args.regex, level=args.level, min_employers=args.min_employers,
    )
    level_note = f", PW_WAGE_LEVEL = {args.level.strip().upper()}" if args.level else " (all wage levels)"
    if not results:
        print(f'[discover_role] no certified filings matched "{args.pattern}"{level_note}')
        return

    print(f'[discover_role] JOB_TITLE ~ "{args.pattern}"{level_note} '
          f"-> {len(results)} SOC code(s) with >= {args.min_employers} employer(s)\n")
    print(f'{"SOC code":<10} {"employers":>9} {"filings":>8}  SOC title')
    for r in results:
        print(f'{r["soc_code"]:<10} {r["employers"]:>9} {r["filings"]:>8}  {r["soc_title"]}')


if __name__ == "__main__":
    run_cli(main)
