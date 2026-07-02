"""Runway — thin caller that builds the grounded entry-wage sponsor shortlist.

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

# Force UTF-8 stdout so non-ASCII (em-dashes in the verify log) doesn't crash on
# a legacy-codepage Windows console (e.g. cp932).
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from engine import verify  # noqa: E402
from engine.sponsors import (  # noqa: E402
    DOL_DATA_PAGE,
    LATEST_QUARTER,
    ROLE_SOC,
    SOC_TITLES,
    build_sponsor_table,
    detect_quarters,
    load_certified_rows,
    quarter_parquet_path,
)

WAGE_LEVEL = "I"
OUT_DIR = Path("output")


def rule(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def no_data_message() -> str:
    return (
        "\nNo converted DOL data found in data/processed/.\n\n"
        "To fix this, download at least one LCA quarter and convert it:\n"
        f"  1. Open  {DOL_DATA_PAGE}\n"
        "     (under 'Disclosure Data' -> LCA Programs (H-1B, H-1B1, E-3)).\n"
        f"     The newest quarter available is {LATEST_QUARTER}. Any FY2021+ quarter works;\n"
        "     a full year of quarters gives the strongest repeat-sponsor signal.\n"
        "  2. Save the .xlsx file(s) into  data/raw/  (keep DOL's original filename).\n"
        "  3. Run:  python scripts/run.py\n"
        "     (that converts, builds the shortlist, and builds the report in one step).\n"
    )


def missing_quarter_message(missing: list[str]) -> str:
    have = detect_quarters()
    lines = [
        f"\nRequested quarter(s) not converted yet: {', '.join(missing)}.",
        "",
        "To fix, either:",
        "  - Drop those quarters' .xlsx into data/raw/ and run:  python scripts/run.py",
        f"    (download them at {DOL_DATA_PAGE} -> Disclosure Data -> LCA Programs).",
    ]
    if have:
        lines.append(f"  - Or omit --quarters to use what's already converted: {', '.join(have)}.")
    else:
        lines.append("  - No quarters are converted yet; run  python scripts/run.py  to set up.")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", default="design", choices=sorted(ROLE_SOC))
    ap.add_argument(
        "--quarters",
        default="",
        help="comma-separated FY####Q# labels; default = every quarter converted "
        "in data/processed/",
    )
    args = ap.parse_args()

    role = args.role
    if args.quarters.strip():
        quarters = [q.strip().upper() for q in args.quarters.split(",") if q.strip()]
    else:
        quarters = detect_quarters()  # run on whatever is present — one quarter is fine
    if not quarters:
        print(no_data_message())
        sys.exit(1)
    soc_codes = ROLE_SOC[role]

    rule("PROVENANCE")
    print(f"role        : {role}")
    print(f"SOC codes   : {', '.join(f'{c} ({SOC_TITLES.get(c, c)})' for c in soc_codes)}")
    print(f"wage level  : {WAGE_LEVEL} (entry-wage; PW_WAGE_LEVEL)")
    print(f"quarters    : {', '.join(quarters)}")
    print("source      : DOL OFLC LCA Programs disclosure data (CASE_STATUS=Certified)")
    for q in quarters:
        p = quarter_parquet_path(q)
        status = "OK" if p.exists() else "MISSING — download this quarter's xlsx, then run scripts/run.py"
        print(f"  {q}: {p}  [{status}]")

    # A requested quarter with no converted parquet is a clean stop, not a traceback.
    missing = [q for q in quarters if not quarter_parquet_path(q).exists()]
    if missing:
        print(missing_quarter_message(missing))
        sys.exit(1)

    # Row-level grounding + aggregated employer table. A bad parquet (wrong or
    # renamed columns — e.g. a PERM file that somehow got converted) is a clean
    # stop with a plain-English message, not a traceback.
    try:
        rows = load_certified_rows(soc_codes, WAGE_LEVEL, quarters)
        table = build_sponsor_table(soc_codes, WAGE_LEVEL, quarters)
    except ValueError as e:
        print("\nCouldn't use the converted data — it doesn't look like DOL LCA data.")
        print(f"  Reason: {e}")
        print("  Delete the file(s) in data/processed/, re-download the LCA Programs")
        print(f"  (H-1B, H-1B1, E-3) quarter from {DOL_DATA_PAGE},")
        print("  and run:  python scripts/run.py")
        sys.exit(1)

    # Empty after filtering is a real, honest answer (the door may simply be
    # closed for this window) — report it plainly instead of crashing.
    if rows.empty or table.empty:
        print(f"\nNo certified entry-wage (Level {WAGE_LEVEL}) {role} filings found in "
              f"{', '.join(quarters)}.")
        print("Either entry-wage sponsorship really is this thin in this window, or this")
        print("isn't the right data. Things worth checking:")
        print("  - Is this the LCA Programs (H-1B, H-1B1, E-3) file, not PERM?")
        print("  - Try a different (or additional) quarter — download from")
        print(f"    {DOL_DATA_PAGE}")
        print("No shortlist was written.")
        sys.exit(1)

    # A failed verification check means the shortlist can't be trusted; stop the
    # run with the failing check spelled out, never a traceback.
    rule("VERIFICATION CELL")
    try:
        for line in verify.run_all(rows, table):
            print(" ", line)
    except verify.VerificationError as e:
        print(f"\nFAILED — {e}")
        print("\nA verification check failed, so this shortlist can't be trusted and")
        print("nothing was written. This usually means the data isn't what it should be")
        print("(wrong file, corrupted download, or a broken conversion). Re-download the")
        print(f"quarter from {DOL_DATA_PAGE} and run:  python scripts/run.py")
        sys.exit(1)

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
