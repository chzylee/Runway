"""Shared plumbing for the scripts: UTF-8 console, repo paths, friendly exits.

Import this before importing `engine` - it puts the repo root on sys.path so
the scripts work when run as `python scripts/<name>.py` from a clean checkout.
"""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_PROCESSED = REPO_ROOT / "data" / "processed"
OUTPUT_DIR = REPO_ROOT / "output"
OUTPUT_PRIVATE = OUTPUT_DIR / "private"

sys.path.insert(0, str(REPO_ROOT))

# Shown on every applicant-facing output, verbatim.
CAVEATS = [
    "An LCA certification is not a hire or an open role.",
    "OPT is not sponsorship — a new grad's first job is on OPT; sponsorship comes 1-3 years later.",
    "Design roles are likely not STEM-OPT eligible -> roughly a 12-month OPT window, not 36.",
    "Employer names are conservatively normalized and may under-merge.",
    "Career/portfolio guidance, not immigration legal advice.",
]


def force_utf8():
    """The locale must never decide whether a run crashes: Japanese-locale
    Windows consoles default to cp932, which cannot print this data."""
    os.environ.setdefault("PYTHONUTF8", "1")
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def ensure_dirs():
    for directory in (DATA_RAW, DATA_PROCESSED, OUTPUT_DIR, OUTPUT_PRIVATE):
        directory.mkdir(parents=True, exist_ok=True)


def run_cli(main):
    """Entry-point wrapper: known failures print their message and exit 1 -
    the user never sees a stack trace for an anticipated failure."""
    force_utf8()
    from engine import RunwayError

    try:
        main()
    except RunwayError as err:
        print(f"\n[stopped] {err}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[stopped] interrupted by user", file=sys.stderr)
        sys.exit(130)
