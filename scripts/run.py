"""THE command: convert -> shortlist -> report, end to end.

    python scripts/run.py

Converts any DOL xlsx dropped in data/raw/, builds and verifies the sponsor
shortlist from every converted quarter, and renders the private report. Never
calls an LLM - the gap read in the report comes from a human-reviewed file
(see prompts/gap_read.md) or renders as a visible placeholder.
"""
import argparse

import _util
from _util import run_cli

import build_report
import build_shortlist
import convert_quarters


def main():
    parser = argparse.ArgumentParser(
        description="Runway v0: DOL xlsx -> sponsor shortlist -> private report."
    )
    parser.add_argument(
        "--quarters",
        help="comma-separated quarters you expect, e.g. FY2025Q4,FY2026Q1; the run stops with "
             "instructions if one has no data. Every converted quarter is always used.",
    )
    parser.add_argument("--force-convert", action="store_true",
                        help="re-convert xlsx files even when their parquet is up to date")
    args = parser.parse_args()
    requested = [q for q in (args.quarters or "").split(",") if q.strip()] or None

    print("[run] Runway v0: convert -> shortlist -> report")
    convert_quarters.convert_all(force=args.force_convert)
    build_shortlist.build(requested_quarters=requested)
    build_report.build_report()
    print("[run] done:")
    print("[run]   output/sponsors_levelI.csv          public shortlist (+ .provenance.json)")
    print("[run]   output/private/runway_report.html   private one-pager")


if __name__ == "__main__":
    run_cli(main)
