"""Build one stored shortlist per title, incrementally, for the GitHub Pages frontend.

This is the v1 multi-title, incremental sibling of build_shortlist.py (which stays
the single-title v0 private-report path). The engine is already title-agnostic -
`build_sponsor_table` takes SOC codes, not a role name - so this script is just the
per-title loop, the stored parquet, and the "already saved?" bookkeeping.

The unit of work is a (title, window) pair. A title's stored parquet is "already
saved" iff it exists AND was built from the current quarter window (the set of
quarters in data/processed/ after cumulative-FYTD supersession). That gives the two
triggers the pipeline promises:

  - a NEW QUARTER shifts the window  -> every title is stale -> all rebuild;
  - a NEW TITLE (added to ROLE_SOC)  -> has no stored parquet -> only it builds;
  - nothing changed                  -> every title matches   -> no-op.

The manifest (output/shortlists/index.json) records, per title, the window it was
built from - that is the saved-state this script diffs against, and it is also what
the frontend reads to know which titles exist. Because it always runs and skips
unchanged titles cheaply, adding a title takes effect on the next pipeline run
without needing a new quarter.
"""
import argparse
import json
from datetime import datetime, timezone

import pandas as pd

import _util
from _util import CAVEATS, DATA_PROCESSED, OUTPUT_DIR, ensure_dirs, run_cli

from engine import RunwayError
from engine.sponsors import (
    ROLE_SOC,
    build_sponsor_table,
    load_quarters,
    supersede_cumulative_quarters,
)
from engine.verify import run_all

WAGE_LEVEL = "I"  # entry wage - the product's whole premise (dec. #2)
SHORTLISTS_DIR = OUTPUT_DIR / "shortlists"
MANIFEST_PATH = SHORTLISTS_DIR / "index.json"


def _parquet_name(title):
    return f"{title}_level{WAGE_LEVEL}.parquet"


def _parquet_reads(path):
    """True iff the stored parquet exists AND reads back. dec. #30: a process killed
    mid-write leaves a truncated parquet; checking only existence would trust and serve
    it forever. The try is scoped to the read alone (mirrors load_quarters' F3 guard,
    dec. #7/#15) and swallows the error into 'rebuild it', never a traceback."""
    if not path.exists():
        return False
    try:
        pd.read_parquet(path)
        return True
    except Exception:
        return False


def _load_manifest():
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            print("[shortlists] manifest unreadable - rebuilding every title")
    return {"titles": {}}


def _empty_entry(title, soc_codes, window, reason):
    """The manifest entry for a title whose filters select zero rows (dec. #25):
    recorded as `empty`, no parquet, so the frontend shows it as a thin/empty role
    instead of the run aborting."""
    return {
        "status": "empty",
        "quarters_built_from": window,
        "soc_codes": sorted(soc_codes),
        "wage_level": WAGE_LEVEL,
        "employer_groups": 0,
        "filings": 0,
        "quarters_superseded": {},
        "parquet": None,
        "reason": reason.splitlines()[0] if reason else "no rows selected",
    }


def _build_one(title, soc_codes, quarters, window):
    """Build and store one title's shortlist parquet; return its manifest entry.

    dec. #25 (call A) splits build failure by kind. build_sponsor_table's only raises
    are "this title's filters selected zero rows" (no certified / no SOC match / no
    wage level) — a NORMAL outcome for a thin niche role, so it is isolated as `empty`
    and the loop keeps building other titles. An integrity-check RunwayError from
    run_all means the engine is miscounting (it corrupts every title), so it is left
    OUTSIDE this try and propagates to abort the whole run — isolate empty, never
    swallow integrity."""
    try:
        table, stats = build_sponsor_table(soc_codes, WAGE_LEVEL, quarters)
    except RunwayError as empty:
        print(f"[shortlists] {title}: {str(empty).splitlines()[0]} -> marking empty, continuing")
        return _empty_entry(title, soc_codes, window, str(empty))

    for check in run_all(table, stats, {label: quarters[label] for label in window}):
        print(f"[verify] {check.status:4} {title}/{check.name} - {check.detail}")

    parquet_path = SHORTLISTS_DIR / _parquet_name(title)
    # dec. #30: write to a .part temp and atomically replace, mirroring
    # fetch_quarters._download — an interrupted write never leaves a truncated file at
    # the real path (the frontend's served data).
    part = parquet_path.with_name(parquet_path.name + ".part")
    table.to_parquet(part, index=False)
    part.replace(parquet_path)
    print(f"[shortlists] {title}: {stats['employer_groups']} employers / "
          f"{stats['rows_selected']} filings -> {parquet_path.relative_to(_util.REPO_ROOT)}")

    return {
        "quarters_built_from": stats["quarters"],
        "soc_codes": sorted(soc_codes),
        "wage_level": WAGE_LEVEL,
        "employer_groups": stats["employer_groups"],
        "filings": stats["rows_selected"],
        "quarters_superseded": stats["quarters_superseded"],
        "parquet": _parquet_name(title),
    }


def build_all(force=False, only_titles=None):
    """Reconcile output/shortlists/ against ROLE_SOC x current window.

    Returns True if anything changed on disk (a title built, rebuilt, or pruned) -
    CI uses this, OR'd with the fetch step, to decide whether to commit.
    """
    ensure_dirs()
    SHORTLISTS_DIR.mkdir(parents=True, exist_ok=True)

    quarters = load_quarters(DATA_PROCESSED)
    kept, _ = supersede_cumulative_quarters(quarters)
    window = sorted(kept)
    print(f"[shortlists] current window: {', '.join(window)}")

    titles = {t: soc for t, soc in ROLE_SOC.items()
              if not only_titles or t in only_titles}

    manifest = _load_manifest()
    prior = manifest.get("titles", {})
    new_titles = {}
    changed = False

    # dec. #29: --titles scopes the BUILD only, never a delete. Carry forward the
    # manifest entry for any title that still exists in ROLE_SOC but is out of this
    # run's build scope, so a scoped run never drops an out-of-subset title.
    for title in ROLE_SOC:
        if title not in titles and title in prior:
            new_titles[title] = prior[title]

    for title, soc_codes in sorted(titles.items()):
        entry = prior.get(title)
        # dec. #26: the saved-state key is (title x definition x window), so editing a
        # title's SOC list (dec. #3) without a new quarter still rebuilds it. soc_codes
        # is stored sorted (see _build_one), so compare against sorted() to avoid a
        # needless rebuild on an order-only difference.
        definition_matches = (
            entry is not None
            and entry.get("quarters_built_from") == window
            and entry.get("soc_codes") == sorted(soc_codes)
            and entry.get("wage_level") == WAGE_LEVEL
        )
        if entry is not None and entry.get("status") == "empty":
            # dec. #25: an already-recorded empty title is saved when its definition +
            # window are unchanged (no parquet to read), so it does not re-detect and
            # flip changed=True on every run.
            up_to_date = not force and definition_matches
        else:
            # dec. #30: gate on the parquet actually READING, not merely existing, so a
            # corrupt-by-crash file is rebuilt (self-heals) instead of skipped and served.
            up_to_date = (
                not force
                and definition_matches
                and _parquet_reads(SHORTLISTS_DIR / _parquet_name(title))
            )
        if up_to_date:
            print(f"[shortlists] {title}: already saved for this window - skipping")
            new_titles[title] = entry
            continue
        new_titles[title] = _build_one(title, soc_codes, kept, window)
        changed = True

    # Prune stored shortlists ONLY for titles removed from the FULL ROLE_SOC
    # registry (dec. #29) — never merely because a --titles subset excluded them.
    # The pipeline owns output/shortlists/, so a genuinely-removed title's parquet
    # must not linger and mislead the frontend; a scoped run must not delete.
    for stale_title in sorted(set(prior) - set(ROLE_SOC)):
        stale_parquet = SHORTLISTS_DIR / prior[stale_title].get("parquet", _parquet_name(stale_title))
        if stale_parquet.exists():
            print(f"[shortlists] pruning removed title: {stale_parquet.name}")
            stale_parquet.unlink()
        changed = True

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "source": "US DOL OFLC LCA Programs disclosure data (public record)",
        "wage_level": WAGE_LEVEL,
        "window": window,
        "caveats": CAVEATS,
        "titles": new_titles,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
    print(f"[shortlists] {'changes written' if changed else 'nothing to do - all titles current'} "
          f"({len(new_titles)} title(s)) -> {MANIFEST_PATH.relative_to(_util.REPO_ROOT)}")

    _emit_github_output(changed)
    return changed


def _emit_github_output(changed):
    import os
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"changed={'true' if changed else 'false'}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Build one stored shortlist parquet per title, incrementally."
    )
    parser.add_argument("--force", action="store_true",
                        help="rebuild every title even if already saved for this window")
    parser.add_argument("--titles",
                        help="comma-separated subset of titles to build (default: all in ROLE_SOC)")
    args = parser.parse_args()
    only = [t.strip() for t in (args.titles or "").split(",") if t.strip()] or None
    build_all(force=args.force, only_titles=only)


if __name__ == "__main__":
    run_cli(main)
