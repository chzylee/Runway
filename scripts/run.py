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

from _util import REPO_ROOT, run_cli

import build_shortlist
import check_caveats_parity
import convert_quarters

PROMPT_TEMPLATE = REPO_ROOT / "prompts" / "recommendations.md"
PROMPT_MIRROR = REPO_ROOT / "web" / "prompts" / "recommendations.md"


def mirror_prompt_template():
    """Mirror the prompt template into the served tree (dec. #35).

    The site fetches `prompts/recommendations.md` relative to its own root, and
    the serve root is web/ (Design Doc §13.3) — the repo-root original is
    unreachable from there. The single source of truth stays
    prompts/recommendations.md (D5); this byte-for-byte copy is a committed
    build artifact like web/data/*, rewritten on every run. Never edit the
    mirror by hand.
    """
    PROMPT_MIRROR.parent.mkdir(parents=True, exist_ok=True)
    PROMPT_MIRROR.write_bytes(PROMPT_TEMPLATE.read_bytes())


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
    # Build check (dec. #34): the prompt template the site fetches (D5) carries the
    # one tolerated second copy of the five caveats; assert it hasn't drifted from the
    # engine's single source before doing any expensive data work. Data-independent,
    # so it fails fast and never leaves a half-built emit behind a late drift error.
    check_caveats_parity.check_caveats_parity()
    # Mirror right after the parity check: the copy is always a template whose
    # caveats were just verified against the engine, and it is data-independent,
    # so it lands even if the convert step later stops the run.
    mirror_prompt_template()
    convert_quarters.convert_all(force=args.force_convert)
    build_shortlist.build(requested_quarters=requested)
    print("[run] done:")
    print("[run]   web/data/design.json             site data (+ .provenance.json, .csv)")
    print("[run]   web/prompts/recommendations.md   prompt-template mirror (do not edit)")
    print("[run]   serve locally: python -m http.server  (rooted at web/)")


if __name__ == "__main__":
    run_cli(main)
