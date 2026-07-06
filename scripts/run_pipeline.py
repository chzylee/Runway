"""Orchestrate the DOL data pipeline's gating decisions in testable Python.

dec. #28 (call E): the convert/commit branching used to live in the GitHub Actions
workflow's `if:` expressions, where it could not be unit-tested - and that gating is
exactly the logic that protects committed data (a wrong "skip convert" serves stale
parquet; a wrong "skip commit" drops a regenerated shortlist). It now lives here as two
pure predicates - should_convert / should_commit - that pytest drives with fabricated
flags, plus a main() that wires the steps in-process using each script's return value.

The workflow shrinks to: checkout -> git config -> python scripts/run_pipeline.py ->
git push. The final push (and its dec. #K rebase-or-retry contract, deferred to v1.1)
stays in the workflow: this module owns the decisions, not the remote plumbing.
"""
import subprocess

from _util import run_cli

import build_shortlists
import convert_quarters
import fetch_quarters


def should_convert(fetch_changed):
    """Convert (stream the 80-140 MB xlsx -> parquet) ONLY when fetch downloaded a new
    quarter: it is the one expensive step, and nothing else produces new parquet."""
    return bool(fetch_changed)


def should_commit(fetch_changed, build_changed):
    """Commit when EITHER a quarter was fetched OR a title's shortlist changed - both
    write version-controlled files (data/processed/, output/shortlists/)."""
    return bool(fetch_changed or build_changed)


def _git(*args):
    subprocess.run(["git", *args], check=True)


def _commit():
    """Stage the pipeline's outputs and commit iff something actually changed on disk.
    The push is the workflow's job (kept out of Python per dec. #28)."""
    _git("add", "data/processed", "output/shortlists")
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 0:
        print("[pipeline] no staged changes after regeneration - nothing to commit")
        return
    _git("commit", "-m", "data: refresh DOL LCA quarters + per-title shortlists [skip ci]")


def main():
    """fetch -> (convert if new quarter) -> build shortlists -> (commit if either
    changed). The gating is the two predicates above, so it is unit-testable in
    isolation from this wiring."""
    fetch_changed = fetch_quarters.fetch()

    if should_convert(fetch_changed):
        convert_quarters.convert_all()
    else:
        print("[pipeline] fetch reported no new quarter - skipping convert")

    build_changed = build_shortlists.build_all()

    if should_commit(fetch_changed, build_changed):
        _commit()
    else:
        print("[pipeline] nothing changed - skipping commit")


if __name__ == "__main__":
    run_cli(main)
