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
    "NAICS_CODE",
    "SECONDARY_ENTITY",
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
    "NAICS_CODE": "541430",           # Graphic Design Services (sector 54)
    "SECONDARY_ENTITY": "No",         # in-house worksite by default
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
    # JOB_TITLE / NAICS_CODE / SECONDARY_ENTITY are set here to drive the dec.#44
    # pattern oracle (EXPECTED["patterns"]); employer, SOC, and wage values are left
    # exactly as they were so the funnel/wage oracle above is unchanged.
    #   "product" recurs across 3 employers -> the one token above the 3-employer floor;
    #   "graphic" spans 2 employers -> below floor, dropped (proves the floor gates);
    #   Café is entirely third-party (agency); Blank Fields sits in NAICS sector 51,
    #   the others in sector 54 -> only 54 clears the floor.
    row(EMPLOYER_NAME="Northwind Design LLC", SOC_CODE="15-1255.00", WAGE_RATE_OF_PAY_FROM="85000",
        JOB_TITLE="Product Designer"),
    # .01 O*NET detail suffix must still count as design (F6 / M2) and stay a DISTINCT
    # occupation in the O*NET split (dec. #44), titled Video Game Designers:
    row(EMPLOYER_NAME="Northwind Design LLC", SOC_CODE="15-1255.01", WAGE_RATE_OF_PAY_FROM="90000",
        SOC_TITLE="Video Game Designers", JOB_TITLE="Product Designer"),
    # second spelling of the same employer -> collapses to one group (employer-collapse):
    row(EMPLOYER_NAME="NORTHWIND DESIGN, INC.", SOC_CODE="27-1024",
        SOC_TITLE="Graphic Designers", WORKSITE_CITY="Dallas", WAGE_RATE_OF_PAY_FROM="88000",
        JOB_TITLE="Graphic Designer"),
    # unicode employer name (M15) + HOUR annualization 45*2080=93600 (M4); third-party site:
    row(EMPLOYER_NAME="Café Studio LLC", SOC_CODE="27-1021",
        SOC_TITLE="Commercial and Industrial Designers", WORKSITE_STATE="CA",
        WORKSITE_CITY="San Diego", WAGE_UNIT_OF_PAY="Hour", WAGE_RATE_OF_PAY_FROM="45.00",
        JOB_TITLE="Product Designer", SECONDARY_ENTITY="Yes"),
    row(EMPLOYER_NAME="Café Studio LLC", SOC_CODE="27-1021",
        SOC_TITLE="Commercial and Industrial Designers", WORKSITE_STATE="CA",
        WORKSITE_CITY="San Diego", WAGE_RATE_OF_PAY_FROM="70000",
        JOB_TITLE="Industrial Designer", SECONDARY_ENTITY="Yes"),
    None,  # padding
    # blank text cells (F5: soc_titles/city must render blank, never "nan") AND
    # an all-excluded wage (Bi-Weekly) so its median renders as an em dash (M14).
    # NAICS 519130 -> sector 51 (Information), the below-floor industry:
    row(EMPLOYER_NAME="Blank Fields Co", SOC_CODE="15-1255.00", SOC_TITLE="",
        WORKSITE_STATE="NY", WORKSITE_CITY="", WAGE_UNIT_OF_PAY="Bi-Weekly",
        WAGE_RATE_OF_PAY_FROM="2400", JOB_TITLE="Product Designer", NAICS_CODE="519130"),
    # Wage Variety: exercises YEAR, MONTH annualization, plus two wage-excluded rows (M4/M14):
    row(EMPLOYER_NAME="Wage Variety LLC", SOC_CODE="27-1024", SOC_TITLE="Graphic Designers",
        WORKSITE_STATE="WA", WORKSITE_CITY="Seattle", WAGE_RATE_OF_PAY_FROM="65000",
        JOB_TITLE="Graphic Designer"),
    row(EMPLOYER_NAME="Wage Variety LLC", SOC_CODE="27-1024", SOC_TITLE="Graphic Designers",
        WORKSITE_STATE="WA", WORKSITE_CITY="Seattle", WAGE_UNIT_OF_PAY="Month", WAGE_RATE_OF_PAY_FROM="6000",
        JOB_TITLE="Graphic Designer"),
    row(EMPLOYER_NAME="Wage Variety LLC", SOC_CODE="27-1024", SOC_TITLE="Graphic Designers",
        WORKSITE_STATE="WA", WORKSITE_CITY="Seattle", WAGE_UNIT_OF_PAY="Bi-Weekly", WAGE_RATE_OF_PAY_FROM="2500",
        JOB_TITLE="Graphic Designer"),
    row(EMPLOYER_NAME="Wage Variety LLC", SOC_CODE="27-1024", SOC_TITLE="Graphic Designers",
        WORKSITE_STATE="WA", WORKSITE_CITY="Seattle", WAGE_RATE_OF_PAY_FROM="",
        JOB_TITLE="Web Designer"),
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
    # dec. #44 title-shortlist patterns, hand-derived from the 10 selected rows and
    # mirroring the emitted object exactly (design.json.patterns == this).
    "patterns": {
        "basis": {"filings": 10, "employers": 4, "measured_by": "employers",
                  "min_support_employers": 3},
        "job_titles": {
            # "product": Northwind + Café + Blank Fields = 3 employers (>= floor).
            # "graphic" (2 employers), "industrial"/"web" (1) fall below and are dropped.
            "recurring_tokens": [
                {"token": "product", "employers": 3, "filings": 4},
            ],
            # verbatim, no stopword, no floor; employers-desc then filings-desc then title.
            "distinct_titles": [
                {"title": "Product Designer", "employers": 3, "filings": 4},
                {"title": "Graphic Designer", "employers": 2, "filings": 4},
                {"title": "Industrial Designer", "employers": 1, "filings": 1},
                {"title": "Web Designer", "employers": 1, "filings": 1},
            ],
        },
        # suffix preserved + bare base canonicalizes to .00; filings-desc. 27-1024.00
        # has 5 filings: Wage Variety's 4 rows (incl. the "Web Designer" title) + Northwind.
        "onet_occupations": [
            {"soc_code": "27-1024.00", "title": "Graphic Designers", "employers": 2, "filings": 5},
            {"soc_code": "15-1255.00", "title": "Web and Digital Interface Designers",
             "employers": 2, "filings": 2},
            {"soc_code": "27-1021.00", "title": "Commercial and Industrial Designers",
             "employers": 1, "filings": 2},
            {"soc_code": "15-1255.01", "title": "Video Game Designers", "employers": 1, "filings": 1},
        ],
        # Café's 2 filings are third-party; the other 8 are in-house.
        "placement_model": {
            "in_house": {"employers": 3, "filings": 8},
            "third_party_site": {"employers": 1, "filings": 2},
        },
        # sector 54 has 3 employers (>= floor); sector 51 (Blank Fields alone) is dropped.
        "industry_naics2": [
            {"code": "54", "label": "Professional, Scientific, and Technical Services",
             "employers": 3, "filings": 9},
        ],
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
