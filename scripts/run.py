"""THE local command: fetch -> convert -> shortlist -> emit web/data/, end to end.

    python scripts/run.py

Checks DOL for any new LCA quarter and downloads it (fetch_quarters.py), converts
every DOL xlsx in data/raw/, builds and verifies the sponsor shortlist from every
converted quarter, and emits three public web/data/ artifacts per registered role
(engine.ROLE_SOC) the static site consumes: <role>.json, <role>.provenance.json,
<role>.csv. v1 has no HTML report - the site is the single presentation surface
(Design Doc D3), served locally with `npm run dev` (see README) - Runway never
calls an LLM and, in v1, never reads a user's file.

`--no-fetch` skips the DOL check (offline work, or a manually-dropped xlsx). CI
runs the fetch as its own gated step and then calls this with `--no-fetch`, so
the expensive convert+build+commit only happens on a run where a new quarter
actually landed - see .github/workflows/data-pipeline.yml.
"""
import argparse

from _util import REPO_ROOT, run_cli

import build_shortlist
import check_caveats_parity
import convert_quarters
import fetch_quarters

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
    parser.add_argument("--no-fetch", action="store_true",
                        help="skip the DOL new-quarter check/download (offline, or a "
                             "manually-dropped xlsx); convert whatever is already in data/raw/")
    args = parser.parse_args()
    requested = [q for q in (args.quarters or "").split(",") if q.strip()] or None

    print("[run] Runway v1: fetch -> convert -> shortlist -> emit web/data/")
    # Build check (dec. #34): the prompt template the site fetches (D5) carries the
    # one tolerated second copy of the five caveats; assert it hasn't drifted from the
    # engine's single source before doing any expensive data work. Data-independent,
    # so it fails fast and never leaves a half-built emit behind a late drift error.
    check_caveats_parity.check_caveats_parity()
    # Mirror right after the parity check: the copy is always a template whose
    # caveats were just verified against the engine, and it is data-independent,
    # so it lands even if the convert step later stops the run.
    mirror_prompt_template()
    # Check DOL for a new quarter and download it before converting (dec. #43).
    # Skipped with --no-fetch for offline work or when CI has already run the fetch
    # as its own gated step. A network/endpoint failure stops the run with a
    # plain-English RunwayError naming README's URL template.
    if not args.no_fetch:
        fetch_quarters.fetch()
    convert_quarters.convert_all(force=args.force_convert)
    built = build_shortlist.build_all(requested_quarters=requested)
    print("[run] done:")
    for role in built:
        print(f"[run]   web/data/{role}/{role}.json   site data (+ .provenance.json, .csv)")
    print("[run]   web/prompts/recommendations.md   prompt-template mirror (do not edit)")
    print("[run]   serve locally: python -m http.server  (rooted at web/)")


if __name__ == "__main__":
    run_cli(main)
