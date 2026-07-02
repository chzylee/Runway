"""Convert raw DOL LCA disclosure xlsx files into narrow parquet quarters.

The source files are 100+ MB, so rows are streamed with openpyxl in read-only
mode instead of loaded whole through pandas.read_excel. Only the columns the
engine needs are kept, resolved by name (column order is not stable across
quarters). The quarter label (FY2025Q4) is derived from DOL's original
filename, LCA_Disclosure_Data_FY<YYYY>_Q<N>.xlsx.
"""
import argparse
import re

import _util
from _util import DATA_PROCESSED, DATA_RAW, ensure_dirs, run_cli

import openpyxl
import pandas as pd

from engine import RunwayError
from engine.sponsors import REQUIRED_COLUMNS
from engine.verify import check_required_columns

_DOL_NAME = re.compile(r"^LCA_Disclosure_Data_FY(\d{4})_Q([1-4])\.xlsx$", re.IGNORECASE)
_PROGRESS_EVERY = 100_000


def convert_file(xlsx_path, parquet_path):
    print(f"[convert] {xlsx_path.name} -> {parquet_path.name} (streaming, this can take a few minutes)")
    try:
        workbook = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    except Exception:
        raise RunwayError(
            f"Could not open {xlsx_path.name} as an xlsx workbook.\n"
            "The download may be incomplete or the file corrupted - re-download it from\n"
            "the DOL disclosure-data page linked in README.md."
        )
    try:
        sheet = workbook.worksheets[0]
        rows = sheet.iter_rows(values_only=True)
        header = next(rows, None)
        if header is None:
            raise RunwayError(f"{xlsx_path.name} contains no rows at all - re-download it?")
        names = [str(cell).strip() if cell is not None else "" for cell in header]
        check_required_columns(names, xlsx_path.name)
        index_of = {name: i for i, name in enumerate(names)}
        picks = [(column, index_of[column]) for column in REQUIRED_COLUMNS]

        columns = {column: [] for column in REQUIRED_COLUMNS}
        row_count = 0
        empty_count = 0
        for row in rows:
            values = [
                None if (i >= len(row) or row[i] is None) else str(row[i]).strip()
                for _, i in picks
            ]
            # DOL xlsx sheets declare far more rows than they hold; the padding
            # comes back as fully empty rows and must not inflate row counts.
            if all(not v for v in values):
                empty_count += 1
                continue
            for column, value in zip(REQUIRED_COLUMNS, values):
                columns[column].append(value)
            row_count += 1
            if row_count % _PROGRESS_EVERY == 0:
                print(f"[convert]   ...{row_count:,} rows")
    finally:
        workbook.close()

    frame = pd.DataFrame(columns, dtype="string")
    frame.to_parquet(parquet_path, index=False)
    size_mb = parquet_path.stat().st_size / 1_000_000
    skipped = f" (skipped {empty_count:,} empty padding rows)" if empty_count else ""
    print(f"[convert]   wrote {len(frame):,} rows -> {parquet_path.name} ({size_mb:.1f} MB){skipped}")


def convert_all(force=False):
    """Convert every DOL-named xlsx in data/raw/ whose parquet is missing or
    older than the source. An empty data/raw/ is not an error here - the
    shortlist step reports missing data with instructions."""
    ensure_dirs()
    xlsx_files = sorted(p for p in DATA_RAW.glob("*.xlsx") if not p.name.startswith("~$"))
    if not xlsx_files:
        print("[convert] no xlsx files in data/raw/ - nothing to convert")
        return
    for xlsx_path in xlsx_files:
        match = _DOL_NAME.match(xlsx_path.name)
        if not match:
            print(
                f"[convert] skipping {xlsx_path.name}: expected DOL's original filename, "
                "LCA_Disclosure_Data_FY<YYYY>_Q<N>.xlsx"
            )
            continue
        parquet_path = DATA_PROCESSED / f"lca_fy{match.group(1)}q{match.group(2)}.parquet"
        if (
            not force
            and parquet_path.exists()
            and parquet_path.stat().st_mtime >= xlsx_path.stat().st_mtime
        ):
            print(f"[convert] {parquet_path.name} is up to date (--force-convert rebuilds it)")
            continue
        convert_file(xlsx_path, parquet_path)


def main():
    parser = argparse.ArgumentParser(description="Convert DOL LCA xlsx files in data/raw/ to parquet.")
    parser.add_argument("--force-convert", action="store_true",
                        help="re-convert even when the parquet is already up to date")
    args = parser.parse_args()
    convert_all(force=args.force_convert)


if __name__ == "__main__":
    run_cli(main)
