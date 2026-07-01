"""Convert downloaded raw DOL LCA xlsx files -> narrow parquet (run once).

Usage:
    python scripts/convert_quarters.py                # convert any missing
    python scripts/convert_quarters.py --force        # reconvert all

Looks for data/raw/LCA_Disclosure_Data_<QUARTER>.xlsx and writes
data/processed/lca_<quarter>.parquet via the engine's streaming converter.
"""

import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.sponsors import quarter_parquet_path, xlsx_to_parquet  # noqa: E402

RAW_DIR = Path("data/raw")
# DOL names files LCA_Disclosure_Data_FY2025_Q4.xlsx; normalize to label FY2025Q4.
FILE_RE = re.compile(r"LCA_Disclosure_Data_(FY\d{4})_?(Q\d)\.xlsx$", re.IGNORECASE)


def main() -> None:
    force = "--force" in sys.argv
    raws = sorted(RAW_DIR.glob("LCA_Disclosure_Data_*.xlsx"))
    if not raws:
        print(f"No raw files in {RAW_DIR}/ — download a DOL LCA quarter first.")
        sys.exit(1)

    for raw in raws:
        m = FILE_RE.search(raw.name)
        if not m:
            print(f"skip (unrecognized name): {raw.name}")
            continue
        quarter = (m.group(1) + m.group(2)).upper()
        out = quarter_parquet_path(quarter)
        if out.exists() and not force:
            print(f"exists, skip: {out}")
            continue
        t0 = time.time()
        n = xlsx_to_parquet(raw, out)
        print(f"converted {quarter}: {n:,} rows -> {out}  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
