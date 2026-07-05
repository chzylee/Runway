"""DOL-shaped xlsx builder + the canonical synthetic fixture rows.

One place defines the shape of a DOL LCA disclosure sheet so the committed
fixture and any on-the-fly xlsx a test needs (cumulative pair for F1, a
wrong-columns PERM decoy for M9) are all written the same way.

The committed fixture models a non-golden quarter (FY2099Q1) on purpose: the
golden check (M11) SKIPS on it, so the integration suite exercises the whole
pipeline without pinning itself to iGavel. Run this module to (re)write the
committed .xlsx:  python tests/dol_xlsx.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONUTF8", "1")

import openpyxl

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
FIXTURE_NAME = "LCA_Disclosure_Data_FY2099_Q1.xlsx"
FIXTURE_PATH = FIXTURES_DIR / FIXTURE_NAME
FIXTURE_QUARTER = "FY2099Q1"

# Column order is deliberately shuffled and salted with two decoy columns
# (CASE_NUMBER, DECISION_DATE) the engine never reads, so conversion is proven
# to resolve the 12 required columns BY NAME, not by position (M8).
HEADER = [
    "DECISION_DATE",
    "EMPLOYER_NAME",
    "CASE_STATUS",
    "SOC_TITLE",
    "WAGE_RATE_OF_PAY_FROM",
    "VISA_CLASS",
    "WORKSITE_STATE",
    "SOC_CODE",
    "CASE_NUMBER",
    "JOB_TITLE",
    "WAGE_UNIT_OF_PAY",
    "WORKSITE_CITY",
    "PW_WAGE_LEVEL",
    "WAGE_RATE_OF_PAY_TO",
]

# A row that would be selected: certified, a design SOC, prevailing-wage Level I.
_GOOD = {
    "DECISION_DATE": "2099-01-15",
    "EMPLOYER_NAME": "Northwind Design LLC",
    "CASE_STATUS": "Certified",
    "SOC_TITLE": "Web and Digital Interface Designers",
    "WAGE_RATE_OF_PAY_FROM": "85000",
    "VISA_CLASS": "H-1B",
    "WORKSITE_STATE": "TX",
    "SOC_CODE": "15-1255.00",
    "CASE_NUMBER": "I-200-99001-000001",
    "JOB_TITLE": "Designer",
    "WAGE_UNIT_OF_PAY": "Year",
    "WORKSITE_CITY": "Austin",
    "PW_WAGE_LEVEL": "I",
    "WAGE_RATE_OF_PAY_TO": "95000",
}


def row(**overrides):
    return {**_GOOD, **overrides}


# `None` entries are fully-empty padding rows (M8: dropped AND counted at
# conversion). They are interspersed so they are not merely trailing rows.
FIXTURE_ROWS = [
    # --- 10 selected filings across 4 employers ---
    row(EMPLOYER_NAME="Northwind Design LLC", SOC_CODE="15-1255.00", WAGE_RATE_OF_PAY_FROM="85000"),
    # .01 O*NET detail suffix must still count as design (F6 / M2):
    row(EMPLOYER_NAME="Northwind Design LLC", SOC_CODE="15-1255.01", WAGE_RATE_OF_PAY_FROM="90000"),
    # second spelling of the same employer -> collapses to one group (employer-collapse):
    row(EMPLOYER_NAME="NORTHWIND DESIGN, INC.", SOC_CODE="27-1024",
        SOC_TITLE="Graphic Designers", WORKSITE_CITY="Dallas", WAGE_RATE_OF_PAY_FROM="88000"),
    # unicode employer name (M15) + HOUR annualization 45*2080=93600 (M4):
    row(EMPLOYER_NAME="Café Studio LLC", SOC_CODE="27-1021",
        SOC_TITLE="Commercial and Industrial Designers", WORKSITE_STATE="CA",
        WORKSITE_CITY="San Diego", WAGE_UNIT_OF_PAY="Hour", WAGE_RATE_OF_PAY_FROM="45.00"),
    row(EMPLOYER_NAME="Café Studio LLC", SOC_CODE="27-1021",
        SOC_TITLE="Commercial and Industrial Designers", WORKSITE_STATE="CA",
        WORKSITE_CITY="San Diego", WAGE_RATE_OF_PAY_FROM="70000"),
    None,  # padding
    # blank text cells (F5: soc_titles/city must render blank, never "nan") AND
    # an all-excluded wage (Bi-Weekly) so its median renders as an em dash (M14):
    row(EMPLOYER_NAME="Blank Fields Co", SOC_CODE="15-1255.00", SOC_TITLE="",
        WORKSITE_STATE="NY", WORKSITE_CITY="", WAGE_UNIT_OF_PAY="Bi-Weekly",
        WAGE_RATE_OF_PAY_FROM="2400"),
    # Wage Variety: exercises YEAR, MONTH annualization, plus two wage-excluded rows (M4/M14):
    row(EMPLOYER_NAME="Wage Variety LLC", SOC_CODE="27-1024", SOC_TITLE="Graphic Designers",
        WORKSITE_STATE="WA", WORKSITE_CITY="Seattle", WAGE_RATE_OF_PAY_FROM="65000"),
    row(EMPLOYER_NAME="Wage Variety LLC", SOC_CODE="27-1024", SOC_TITLE="Graphic Designers",
        WORKSITE_STATE="WA", WORKSITE_CITY="Seattle", WAGE_UNIT_OF_PAY="Month", WAGE_RATE_OF_PAY_FROM="6000"),
    row(EMPLOYER_NAME="Wage Variety LLC", SOC_CODE="27-1024", SOC_TITLE="Graphic Designers",
        WORKSITE_STATE="WA", WORKSITE_CITY="Seattle", WAGE_UNIT_OF_PAY="Bi-Weekly", WAGE_RATE_OF_PAY_FROM="2500"),
    row(EMPLOYER_NAME="Wage Variety LLC", SOC_CODE="27-1024", SOC_TITLE="Graphic Designers",
        WORKSITE_STATE="WA", WORKSITE_CITY="Seattle", WAGE_RATE_OF_PAY_FROM=""),
    None,  # padding
    # --- 5 rows that must NOT be selected (fill out the funnel) ---
    # "Certified - Withdrawn" is deliberately excluded (dec. #2 / M1):
    row(EMPLOYER_NAME="Withdrawn Design LLC", CASE_STATUS="Certified - Withdrawn"),
    row(EMPLOYER_NAME="Denied Design LLC", CASE_STATUS="Denied"),
    # certified design but Level II -> excluded by wage level (M3):
    row(EMPLOYER_NAME="LevelTwo Design LLC", PW_WAGE_LEVEL="II"),
    # certified Level I but a non-design SOC -> excluded by SOC (M2):
    row(EMPLOYER_NAME="Statistician Co", SOC_CODE="15-2041.00", SOC_TITLE="Statisticians"),
    row(EMPLOYER_NAME="Withdrawn2 Co", CASE_STATUS="Withdrawn"),
]

# Facts the integration tests assert against, derived by hand from FIXTURE_ROWS
# above and confirmed by the engine prototype. Kept here so a change to the
# fixture and its expected funnel move together.
EXPECTED = {
    "rows_total": 15,        # 17 sheet rows - 2 empty padding
    "empty_padding": 2,
    "rows_certified": 12,    # 10 selected + LevelTwo + Statistician
    "rows_soc_matched": 11,  # 10 selected + LevelTwo (design SOC, wrong level)
    "rows_selected": 10,
    "employer_groups": 4,
    "distinct_raw_employers": 5,
    "rows_wage_excluded": 3,  # 2 in Wage Variety + Blank Fields' Bi-Weekly filing
    # employer_display -> (filing_count, wage_min, wage_median, wage_max);
    # None means all filings were wage-excluded (renders as an em dash).
    "employers": {
        "Wage Variety LLC": (4, 65000, 68500, 72000),
        "Northwind Design LLC": (3, 85000, 88000, 90000),
        "Café Studio LLC": (2, 70000, 81800, 93600),
        "Blank Fields Co": (1, None, None, None),
    },
}

# A PERM-style header: right kind of file name, wrong columns. check_required_columns
# must reject it (M9 / S4 rationale). Shares only incidental columns with LCA.
PERM_HEADER = [
    "CASE_NUMBER", "CASE_STATUS", "EMPLOYER_NAME", "PW_SOC_CODE",
    "PW_SOC_TITLE", "PW_LEVEL", "JOB_INFO_WORK_STATE", "COUNTRY_OF_CITIZENSHIP",
]


def write_xlsx(path, rows, header=None):
    """Write a single-sheet DOL-shaped xlsx. `rows` items are dicts (data rows)
    or None (a fully-empty padding row). Missing keys are written as empty cells.
    """
    header = header or HEADER
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "LCA"
    sheet.append(header)
    for item in rows:
        if item is None:
            sheet.append([None] * len(header))
        else:
            sheet.append([item.get(col) for col in header])
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def regenerate():
    write_xlsx(FIXTURE_PATH, FIXTURE_ROWS)
    print(f"wrote {FIXTURE_PATH} ({len(FIXTURE_ROWS)} sheet rows, header {len(HEADER)} cols)")


if __name__ == "__main__":
    regenerate()
    sys.exit(0)
