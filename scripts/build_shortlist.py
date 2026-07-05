"""Build output/sponsors_levelI.csv from the converted quarters.

Runs the engine over every quarter found in data/processed/, verifies the
result (a failed check stops the run), and writes the public shortlist CSV
plus a provenance JSON describing exactly what the numbers were derived from.
"""
import argparse
import json
from datetime import datetime, timezone

import _util
from _util import CAVEATS, DATA_PROCESSED, OUTPUT_DIR, ensure_dirs, run_cli

from engine.sponsors import ROLE_SOC, build_sponsor_table, load_quarters
from engine.verify import run_all

CSV_PATH = OUTPUT_DIR / "sponsors_levelI.csv"
PROVENANCE_PATH = OUTPUT_DIR / "sponsors_levelI.provenance.json"

ROLE = "design"
WAGE_LEVEL = "I"


def build(requested_quarters=None):
    ensure_dirs()
    quarters = load_quarters(DATA_PROCESSED, requested_quarters)
    print(f"[shortlist] quarters loaded: {', '.join(sorted(quarters))}")

    table, stats = build_sponsor_table(ROLE_SOC[ROLE], WAGE_LEVEL, quarters)
    for dropped, kept in sorted(stats["quarters_superseded"].items()):
        print(f"[shortlist] {dropped} superseded by cumulative {kept} (same fiscal year; "
              "DOL files are FYTD) - using the latest to avoid double-counting")
    for check in run_all(table, stats, quarters):
        print(f"[verify] {check.status:4} {check.name} - {check.detail}")

    table.to_csv(CSV_PATH, index=False, encoding="utf-8", lineterminator="\n")

    provenance = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "source": "US DOL OFLC LCA Programs disclosure data (public record)",
        "filters": {
            "case_status": "Certified",
            "role": ROLE,
            "soc_codes": ROLE_SOC[ROLE],
            "pw_wage_level": WAGE_LEVEL,
        },
        "quarters_used": stats["quarters"],
        "quarters_superseded": stats["quarters_superseded"],
        "rows_per_quarter": stats["rows_per_quarter"],
        "funnel": {
            "rows_total": stats["rows_total"],
            "rows_certified": stats["rows_certified"],
            "rows_soc_matched": stats["rows_soc_matched"],
            "rows_selected": stats["rows_selected"],
        },
        "employer_groups": stats["employer_groups"],
        "distinct_raw_employer_spellings": stats["distinct_raw_employers"],
        "rows_wage_excluded_from_wage_stats": stats["rows_wage_excluded"],
        "case_statuses_seen": stats["case_statuses_seen"],
        "wage_levels_seen": stats["wage_levels_seen"],
        "wage_units_seen": stats["wage_units_seen"],
        "caveats": CAVEATS,
    }
    PROVENANCE_PATH.write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")

    print(
        f"[shortlist] {stats['employer_groups']} employers / {stats['rows_selected']} filings "
        f"-> {CSV_PATH.relative_to(_util.REPO_ROOT)}"
    )
    return table, stats


def main():
    parser = argparse.ArgumentParser(description="Build the Level-I design sponsor shortlist.")
    parser.add_argument(
        "--quarters",
        help="comma-separated quarters you expect, e.g. FY2025Q4,FY2026Q1; the run stops with "
             "instructions if one has no converted data. Every converted quarter is always used.",
    )
    args = parser.parse_args()
    requested = [q for q in (args.quarters or "").split(",") if q.strip()] or None
    build(requested_quarters=requested)


if __name__ == "__main__":
    run_cli(main)
