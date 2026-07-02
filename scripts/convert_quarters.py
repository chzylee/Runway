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

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

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
        try:
            n = xlsx_to_parquet(raw, out)
        except ValueError as e:
            print(f"\nCouldn't use {raw.name} — it doesn't look like a DOL LCA disclosure file.")
            print(f"  Reason: {e}")
            print("  Make sure it's the LCA Programs (H-1B, H-1B1, E-3) file — not PERM or")
            print("  prevailing-wage — from")
            print("  https://www.dol.gov/agencies/eta/foreign-labor/performance (Disclosure Data).")
            sys.exit(1)
        except Exception as e:
            print(f"\nCouldn't read {raw.name}: {e}")
            print("  The file may be corrupted or incomplete — re-download it from")
            print("  https://www.dol.gov/agencies/eta/foreign-labor/performance and try again.")
            sys.exit(1)
        print(f"converted {quarter}: {n:,} rows -> {out}  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
