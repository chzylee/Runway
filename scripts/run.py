"""THE local command: convert -> shortlist -> emit web/data/, end to end.

    python scripts/run.py

Converts any DOL xlsx dropped in data/raw/, builds and verifies the sponsor
shortlist from every converted quarter, and emits the three public web/data/
artifacts the static site consumes (design.json, design.provenance.json,
design.csv). v1 has no HTML report - the site is the single presentation
surface (Design Doc D3), served with `python -m http.server` rooted at web/.
Runway never calls an LLM and, in v1, never reads a user's file.
"""
import argparse

from _util import run_cli

import build_shortlist
import convert_quarters


def main():
    parser = argparse.ArgumentParser(
        description="Runway v1: DOL xlsx -> sponsor shortlist -> web/data/ artifacts."
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

    print("[run] Runway v1: convert -> shortlist -> emit web/data/")
    convert_quarters.convert_all(force=args.force_convert)
    build_shortlist.build(requested_quarters=requested)
    print("[run] done:")
    print("[run]   web/data/design.json             site data (+ .provenance.json, .csv)")
    print("[run]   serve locally: python -m http.server  (rooted at web/)")


if __name__ == "__main__":
    run_cli(main)
