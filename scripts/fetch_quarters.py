"""Discover and download the DOL LCA quarters this repo should hold.

This is the automated replacement for the manual "download from DOL and drop it
in data/raw/" step (README "Get the data"). It exists because CI has no human to
drop files: a fresh runner starts with an empty data/raw/, so it must discover
what is *published upstream* on its own.

Discovery uses DOL's stable direct-link template (README.md), HEAD-probed so a
200 means "this quarter is published" and a 404 means "not yet":

    https://www.dol.gov/sites/dolgov/files/ETA/oflc/pdfs/LCA_Disclosure_Data_FY<YYYY>_Q<N>.xlsx

Incrementality is keyed on **quarter identity**, not mtime. In CI, git does not
preserve mtimes and the 80-140 MB xlsx are never committed, so the mtime skip in
convert_quarters.py cannot see "new data." Instead we compare the quarters that
exist upstream against the parquet already committed in data/processed/ and
download only what is missing.

DOL files are cumulative fiscal-year-to-date (FY2026 Q2 contains Q1), so we keep
only the **highest available quarter per fiscal year** and prune a superseded
same-FY parquet when a newer one lands - the storage-side of the supersede rule
the engine already applies at aggregation (docs/decision_log.md, dec. #21).

Local operators do not need this - dropping an xlsx in data/raw/ by hand still
works exactly as before. This only automates the drop for the pipeline.
"""
import argparse
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

import _util
from _util import DATA_PROCESSED, DATA_RAW, ensure_dirs, run_cli

from engine import RunwayError
from engine.sponsors import discover_quarters

# How many fiscal years back to keep (current FY + this many prior). DOL data is
# FYTD-cumulative, so this is "years of coverage," not "quarters."
LOOKBACK_FISCAL_YEARS = 1  # -> current FY and the one before it

_URL_TEMPLATE = (
    "https://www.dol.gov/sites/dolgov/files/ETA/oflc/pdfs/"
    "LCA_Disclosure_Data_FY{fy}_Q{q}.xlsx"
)
# A courteous, identifiable UA - we hit a public .gov endpoint a handful of
# times a week; anonymous scraping-style requests are worth avoiding.
_USER_AGENT = "Runway-data-pipeline/1 (+https://github.com/; DOL LCA disclosure data)"
_TIMEOUT = 60
_LABEL = re.compile(r"^FY(\d{4})Q([1-4])$")  # committed-parquet quarter label


def current_fiscal_year(today=None):
    """DOL fiscal year N runs Oct 1 (N-1) through Sep 30 (N); Oct-Dec is Q1."""
    today = today or datetime.now(timezone.utc)
    return today.year + 1 if today.month >= 10 else today.year


def _request(url, method):
    return urllib.request.Request(url, method=method, headers={"User-Agent": _USER_AGENT})


def quarter_is_published(fy, q):
    """HEAD-probe one quarter's URL. True iff DOL serves it (HTTP 200)."""
    url = _URL_TEMPLATE.format(fy=fy, q=q)
    try:
        with urllib.request.urlopen(_request(url, "HEAD"), timeout=_TIMEOUT) as resp:
            return resp.status == 200, url
    except urllib.error.HTTPError:
        return False, url
    except urllib.error.URLError as err:
        raise RunwayError(
            f"Could not reach DOL to check FY{fy} Q{q} ({url}).\n"
            f"Network/endpoint error: {err.reason}. The disclosure-data host may be "
            "down or the URL template may have changed - verify README.md's link."
        )


def discover_upstream(fiscal_years):
    """For each fiscal year, find the highest published quarter (cumulative FYTD).
    Returns {label: (fy, q, url)}, e.g. {"FY2026Q1": (2026, 1, "https://...")}."""
    latest = {}
    for fy in fiscal_years:
        for q in (4, 3, 2, 1):  # newest-first; first 200 is the cumulative file
            published, url = quarter_is_published(fy, q)
            if published:
                latest[f"FY{fy}Q{q}"] = (fy, q, url)
                print(f"[fetch] upstream: FY{fy} latest published quarter is Q{q}")
                break
        else:
            print(f"[fetch] upstream: FY{fy} not published yet (no quarter found)")
    return latest


def _download(url, dest):
    """Stream a large xlsx to disk via a .part temp, then atomically rename -
    an interrupted download never leaves a truncated file that looks complete."""
    part = dest.with_suffix(dest.suffix + ".part")
    print(f"[fetch] downloading {url}")
    print(f"[fetch]   -> {dest.name} (80-140 MB, streamed)")
    try:
        with urllib.request.urlopen(_request(url, "GET"), timeout=_TIMEOUT) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            got = 0
            with open(part, "wb") as fh:
                while True:
                    chunk = resp.read(1 << 20)  # 1 MB
                    if not chunk:
                        break
                    fh.write(chunk)
                    got += len(chunk)
    except urllib.error.URLError as err:
        part.unlink(missing_ok=True)
        raise RunwayError(f"Download failed for {url}: {getattr(err, 'reason', err)}")
    if total and got != total:
        part.unlink(missing_ok=True)
        raise RunwayError(
            f"Download of {dest.name} was truncated ({got:,} of {total:,} bytes). Re-run."
        )
    part.replace(dest)
    print(f"[fetch]   wrote {got / 1_000_000:.1f} MB -> {dest.name}")


def fetch(force=False):
    """Reconcile data/processed against what DOL publishes; download the gap.

    Returns True if anything changed on disk (a quarter downloaded or a
    superseded parquet pruned) - the caller (CI) uses this to decide whether to
    run the expensive convert+shortlist steps and commit at all.
    """
    ensure_dirs()
    fy_now = current_fiscal_year()
    fiscal_years = list(range(fy_now, fy_now - LOOKBACK_FISCAL_YEARS - 1, -1))
    print(f"[fetch] current fiscal year FY{fy_now}; window: "
          f"{', '.join(f'FY{y}' for y in fiscal_years)}")

    upstream = discover_upstream(fiscal_years)
    if not upstream:
        raise RunwayError(
            "DOL published no LCA quarters in the lookback window - this should not "
            "happen. Verify README.md's URL template still resolves."
        )

    have = discover_quarters(DATA_PROCESSED)  # {label: parquet_path}
    changed = False

    # 1. Download quarters that are published but not yet converted.
    for label, (fy, q, url) in sorted(upstream.items()):
        if label in have and not force:
            print(f"[fetch] {label} already converted (data/processed) - skipping")
            continue
        dest = DATA_RAW / f"LCA_Disclosure_Data_FY{fy}_Q{q}.xlsx"
        _download(url, dest)
        changed = True

    # 2. Conservative prune (dec. #27): remove a committed parquet ONLY for a
    #    provably-safe reason and NEVER because a probe missed this run. DOL serves
    #    stable permanent links and never un-publishes a quarter, so "present locally,
    #    absent upstream this run" is a transient failure to survive (5xx/429/timeout),
    #    not a signal to delete - dropping an in-window FY collapses the repeat-sponsor
    #    floor (>= 2 fiscal years, dec. #10/#21). The two safe reasons:
    #      (a) supersession - a NEWER same-FY quarter was positively observed (a 200),
    #          so the older same-FY file is redundant (cumulative FYTD, dec. #21);
    #      (b) out-of-window - the FY is older than the lookback floor (pure calendar
    #          math, independent of any probe).
    floor_fy = fy_now - LOOKBACK_FISCAL_YEARS
    upstream_latest_q = {fy: q for fy, q, _ in upstream.values()}
    for label, path in sorted(have.items()):
        m = _LABEL.match(label)
        if not m:
            continue
        fy, q = int(m.group(1)), int(m.group(2))
        out_of_window = fy < floor_fy
        superseded = fy in upstream_latest_q and upstream_latest_q[fy] > q
        if out_of_window or superseded:
            reason = "out-of-window" if out_of_window else "superseded same-FY"
            print(f"[fetch] pruning {reason} parquet: {path.name}")
            path.unlink()
            changed = True

    print(f"[fetch] {'changes staged' if changed else 'nothing to do - already current'}")
    _emit_github_output(changed)
    return changed


def _emit_github_output(changed):
    """When running under GitHub Actions, expose `changed` so later steps can
    gate on it (`if: steps.fetch.outputs.changed == 'true'`)."""
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"changed={'true' if changed else 'false'}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Discover and download the DOL LCA quarters this repo should hold."
    )
    parser.add_argument("--force", action="store_true",
                        help="re-download even quarters already converted")
    args = parser.parse_args()
    fetch(force=args.force)


if __name__ == "__main__":
    run_cli(main)
