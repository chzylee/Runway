"""Runway — the one command. Convert -> shortlist -> report, end to end.

For a non-technical user this is the whole tool: download a DOL quarter into
data/raw/, then run

    python scripts/run.py

It figures out what still needs converting, builds the grounded shortlist from
whatever quarters are present (one is enough), and builds the HTML report. If
there's no data yet, it says exactly where to get it instead of failing with a
stack trace.
"""

import os
import subprocess
import sys
from pathlib import Path

# Windows consoles default to a legacy locale codepage (e.g. cp932 on JP
# systems) that can't encode the em-dashes etc. in our output. Force UTF-8 so
# the tool doesn't crash on non-ASCII regardless of the machine's locale.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.sponsors import detect_quarters  # noqa: E402

RAW_DIR = ROOT / "data" / "raw"
REPORT_PATH = ROOT / "output" / "private" / "runway_report.html"
DOL_DATA_PAGE = "https://www.dol.gov/agencies/eta/foreign-labor/performance"
LATEST_QUARTER = "FY2026 Q2"


def step(title: str) -> None:
    print(f"\n{'#' * 70}\n# {title}\n{'#' * 70}")


def run_script(name: str) -> None:
    """Run a sibling script with this same Python; stop the whole run if it fails."""
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / name)], cwd=ROOT, env=env)
    if result.returncode != 0:
        print(f"\nStopped: {name} failed (exit {result.returncode}). Nothing above was published.")
        sys.exit(result.returncode)


def no_data_message() -> None:
    have_raw = list(RAW_DIR.glob("LCA_Disclosure_Data_*.xlsx")) if RAW_DIR.exists() else []
    print("\nNo DOL data to build from yet.\n")
    print("Do this once:")
    print(f"  1. Open  {DOL_DATA_PAGE}")
    print("     Under 'Disclosure Data', find LCA Programs (H-1B, H-1B1, E-3).")
    print(f"     Newest quarter available: {LATEST_QUARTER}. Any FY2021+ quarter works;")
    print("     downloading a full year of quarters gives the strongest signal.")
    print(f"  2. Save the .xlsx file(s) into:  {RAW_DIR}")
    print("     Keep DOL's original filename (e.g. LCA_Disclosure_Data_FY2026_Q2.xlsx).")
    print("  3. Run this command again:  python scripts/run.py")
    if have_raw:
        print(f"\n(Note: found {len(have_raw)} raw file(s) but no converted quarters — "
              "conversion may have failed above.)")


def main() -> None:
    step("STEP 1/3  Convert raw DOL xlsx -> parquet")
    if not RAW_DIR.exists() or not list(RAW_DIR.glob("LCA_Disclosure_Data_*.xlsx")):
        no_data_message()
        sys.exit(1)
    run_script("convert_quarters.py")

    if not detect_quarters():
        no_data_message()
        sys.exit(1)

    step("STEP 2/3  Build the grounded sponsor shortlist")
    run_script("build_shortlist.py")

    step("STEP 3/3  Build the HTML report")
    run_script("build_report.py")

    step("DONE")
    print(f"Quarters used : {', '.join(detect_quarters())}")
    print("Shortlist CSV : output/sponsors_levelI.csv")
    print(f"Report        : {REPORT_PATH}")
    print("\nOpen the report in a browser to read it. To add your portfolio gap-read,")
    print("follow step 4 in the README (prompts/gap_read.md), then run this again.")


if __name__ == "__main__":
    main()
