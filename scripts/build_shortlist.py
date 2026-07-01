"""Stay Here — thin caller that builds the grounded entry-wage sponsor shortlist.

This is the "notebook" reduced to a script: it prints full provenance (source
files + quarters + row counts), calls the engine, runs the verification cell,
and writes the public artifact sponsors_levelI.csv. A failed verification check
raises and stops the run.

Usage:
    python scripts/build_shortlist.py
    python scripts/build_shortlist.py --role design --quarters FY2025Q1,FY2025Q2,FY2025Q3,FY2025Q4
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from engine import verify  # noqa: E402
from engine.sponsors import (  # noqa: E402
    ROLE_SOC,
    SOC_TITLES,
    build_sponsor_table,
    load_certified_rows,
    quarter_parquet_path,
)

DEFAULT_QUARTERS = ["FY2025Q1", "FY2025Q2", "FY2025Q3", "FY2025Q4"]
WAGE_LEVEL = "I"
OUT_DIR = Path("output")


def rule(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", default="design", choices=sorted(ROLE_SOC))
    ap.add_argument("--quarters", default=",".join(DEFAULT_QUARTERS))
    args = ap.parse_args()

    role = args.role
    quarters = [q.strip().upper() for q in args.quarters.split(",") if q.strip()]
    soc_codes = ROLE_SOC[role]

    rule("PROVENANCE")
    print(f"role        : {role}")
    print(f"SOC codes   : {', '.join(f'{c} ({SOC_TITLES.get(c, c)})' for c in soc_codes)}")
    print(f"wage level  : {WAGE_LEVEL} (entry-wage; PW_WAGE_LEVEL)")
    print(f"quarters    : {', '.join(quarters)}")
    print("source      : DOL OFLC LCA Programs disclosure data (CASE_STATUS=Certified)")
    for q in quarters:
        p = quarter_parquet_path(q)
        status = "OK" if p.exists() else "MISSING — run scripts/convert_quarters.py"
        print(f"  {q}: {p}  [{status}]")

    # Row-level grounding + aggregated employer table.
    rows = load_certified_rows(soc_codes, WAGE_LEVEL, quarters)
    table = build_sponsor_table(soc_codes, WAGE_LEVEL, quarters)

    rule("VERIFICATION CELL")
    for line in verify.run_all(rows, table):
        print(" ", line)

    rule("RESULT")
    print(f"selected certified Level-I {role} filings : {len(rows):,}")
    print(f"distinct sponsor employers                : {len(table):,}")
    multi = table[table["quarters_present"] >= 2]
    print(f"repeat sponsors (>=2 quarters)            : {len(multi):,}")
    print("\nTop 20 by quarters present, then filing count:")
    show = table.head(20)[["employer", "filing_count", "quarters_present", "soc_titles", "worksite_states"]]
    with pd.option_context("display.max_colwidth", 40, "display.width", 200):
        print(show.to_string(index=False))

    # Artifacts (public, DOL-derived — not her personal data).
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    table_path = OUT_DIR / "sponsors_levelI.csv"
    rows_path = OUT_DIR / "sponsors_levelI_rows.csv"
    table.to_csv(table_path, index=False)
    rows[
        ["QUARTER", "EMPLOYER_NAME", "EMP_NORM", "SOC7", "SOC_TITLE", "JOB_TITLE",
         "WORKSITE_CITY", "WORKSITE_STATE", "WAGE_ANNUAL", "VISA_CLASS"]
    ].to_csv(rows_path, index=False)

    rule("ARTIFACTS WRITTEN")
    print(f"  {table_path}  ({len(table)} employers)")
    print(f"  {rows_path}   ({len(rows)} filings — gap-read grounding)")


if __name__ == "__main__":
    main()
