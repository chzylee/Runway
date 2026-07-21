"""Deterministic sponsor engine over converted DOL LCA disclosure quarters.

Reads narrow parquet files from data/processed/, filters to certified
entry-wage filings for a role's SOC codes, and aggregates one row per
normalized employer. Pure data in, data out - no LLM, no HTML, no printing.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pandas as pd

from engine import RunwayError

# Columns kept from the DOL xlsx, always resolved BY NAME - column order is
# not stable across quarters.
REQUIRED_COLUMNS = [
    "CASE_STATUS",
    "VISA_CLASS",
    "JOB_TITLE",
    "SOC_CODE",
    "SOC_TITLE",
    "EMPLOYER_NAME",
    "WORKSITE_CITY",
    "WORKSITE_STATE",
    "WAGE_RATE_OF_PAY_FROM",
    "WAGE_RATE_OF_PAY_TO",
    "WAGE_UNIT_OF_PAY",
    "PW_WAGE_LEVEL",
]

# Adding a role later = one new entry here. All SOC codes within a role are
# treated equally; listing order carries no meaning.
ROLE_SOC = {
    "design": ["15-1255", "27-1024", "27-1021"],
    # Narrower subset view of "design" (dec. #39): no SOC/O*NET code is scoped to
    # "UI/UX" specifically, so this reuses 15-1255 (Web and Digital Interface
    # Designers) alone — the closest official match, and what "UI/UX" colloquially
    # means. Same detail-suffix consequence as "design" (dec. #3 amendment):
    # Video Game Designers (15-1255.01) is included too.
    "uiux": ["15-1255"],
}

# Annualization multipliers for WAGE_UNIT_OF_PAY. A unit outside this map
# (DOL also publishes e.g. "Bi-Weekly") keeps the filing in every count but
# contributes no wage statistics - see docs/decision_log.md.
WAGE_UNIT_TO_ANNUAL = {"YEAR": 1, "HOUR": 2080, "MONTH": 12, "WEEK": 52}

# Only these trailing tokens are stripped when grouping employer names.
# Deliberately conservative (LLP, PLLC, CO, GMBH, ... are kept) so that
# distinct employers never merge; the cost is occasional under-merging.
CORPORATE_SUFFIXES = {"LLC", "INC", "CORP", "LTD"}

_NON_ALNUM = re.compile(r"[^A-Z0-9]+")
_ARABIC_TO_ROMAN = {"1": "I", "2": "II", "3": "III", "4": "IV"}
_ROMAN_LEVELS = set(_ARABIC_TO_ROMAN.values())
_PARQUET_NAME = re.compile(r"^lca_fy(\d{4})q([1-4])\.parquet$", re.IGNORECASE)
_QUARTER_LABEL = re.compile(r"^FY(\d{4})Q([1-4])$", re.IGNORECASE)


def normalize_employer(name) -> str:
    """Group key for an employer: uppercase, punctuation collapsed to spaces,
    trailing corporate suffixes stripped."""
    tokens = _NON_ALNUM.sub(" ", str(name).upper()).split()
    while len(tokens) > 1 and tokens[-1] in CORPORATE_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def normalize_wage_level(value):
    """Map the year-to-year spellings of a prevailing-wage level ("I",
    "Level I", 1, "1.0", ...) onto "I".."IV"; anything else becomes None."""
    if value is None:
        return None
    s = str(value).strip().upper()
    if s.startswith("LEVEL"):
        s = s[len("LEVEL"):].strip()
    if s.endswith(".0"):  # numeric xlsx cells round-trip as "1.0"
        s = s[:-2]
    if s in _ARABIC_TO_ROMAN:
        return _ARABIC_TO_ROMAN[s]
    if s in _ROMAN_LEVELS:
        return s
    return None


def normalize_soc(code) -> str:
    # Some quarters publish SOC codes with a ".00" detail suffix.
    return "" if code is None else str(code).strip().split(".")[0]


def _clean(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip()


def _top_values(series: pd.Series, n: int = 6) -> str:
    counts = Counter(v if v else "(blank)" for v in _clean(series))
    return ", ".join(f'"{value}" ({count} rows)' for value, count in counts.most_common(n))


def _distinct_joined(series: pd.Series) -> str:
    return "; ".join(sorted({v for v in _clean(series) if v}))


def discover_quarters(processed_dir) -> dict[str, Path]:
    """Map quarter label (e.g. "FY2025Q4") -> parquet path for every converted
    quarter present, whatever was or wasn't asked for."""
    processed_dir = Path(processed_dir)
    found = {}
    if processed_dir.is_dir():
        for path in sorted(processed_dir.glob("*.parquet")):
            m = _PARQUET_NAME.match(path.name)
            if m:
                found[f"FY{m.group(1)}Q{m.group(2)}"] = path
    return found


def load_quarters(processed_dir, requested=None) -> dict[str, pd.DataFrame]:
    """Load every converted quarter found in processed_dir.

    `requested` is an optional list of quarter labels the caller expects to be
    present: a requested quarter with no parquet stops the run with
    instructions, while an extra quarter that wasn't requested is simply used.
    """
    found = discover_quarters(processed_dir)
    if requested:
        wanted = [q.strip().upper().replace(" ", "") for q in requested if q and q.strip()]
        missing = sorted(set(wanted) - set(found))
        if missing:
            raise RunwayError(
                f"Requested quarter(s) not converted yet: {', '.join(missing)}.\n"
                "To add a quarter: download its LCA_Disclosure_Data_FY<YYYY>_Q<N>.xlsx from the\n"
                "DOL disclosure-data page (link in README.md), drop it into data/raw/, and run:\n"
                "  python scripts/run.py"
            )
    if not found:
        raise RunwayError(
            "No converted LCA data found in data/processed/.\n"
            "Download a quarter (e.g. LCA_Disclosure_Data_FY2025_Q4.xlsx) from the DOL\n"
            "disclosure-data page (link in README.md), drop it into data/raw/, and run:\n"
            "  python scripts/run.py"
        )
    quarters = {}
    for label, path in found.items():
        # Scope the try to the read alone: a truncated/corrupt parquet (an
        # interrupted conversion leaves a half-written one) raises a raw pyarrow
        # error here, which would leak as a traceback. The corrupt file is newer
        # than its xlsx, so a plain re-run hits the mtime skip and reuses it -
        # --force-convert is the only escape (dec. #7/#15). Nothing but the read
        # lives in the try, so a bug in our own aggregation is never masked.
        try:
            df = pd.read_parquet(path)
        except Exception:
            raise RunwayError(
                f"{path.name} could not be read - it is probably truncated or corrupted "
                "(an interrupted conversion can leave a half-written parquet).\n"
                "Rebuild it from the source xlsx with:\n"
                "  python scripts/run.py --force-convert"
            )
        missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing_cols:
            raise RunwayError(
                f"{path.name} is missing column(s): {', '.join(missing_cols)}.\n"
                "It was probably written by an older version of this tool. Rebuild it with:\n"
                "  python scripts/run.py --force-convert"
            )
        quarters[label] = df
    return quarters


def supersede_cumulative_quarters(quarters):
    """DOL quarterly files are cumulative fiscal-year-to-date: within one fiscal
    year the latest quarter file already contains every earlier same-FY filing.
    Keep only that latest file per fiscal year - loading an earlier same-FY
    quarter alongside it counts shared filings twice and fabricates the
    repeat_sponsor signal (F1/I8; dec. #21). Different fiscal years are always
    kept, so repeat = present in >= 2 distinct fiscal years.

    Returns (kept, superseded): the {label: frame} to actually use, and a
    {dropped_label: superseding_label} map so the caller can report exactly what
    was collapsed - nothing disappears silently (dec. #16).
    """
    latest = {}  # fiscal year -> (quarter number, label)
    for label in quarters:
        m = _QUARTER_LABEL.match(label)
        fy = m.group(1) if m else label          # unparseable labels stand alone
        q = int(m.group(2)) if m else 0
        if fy not in latest or q > latest[fy][0]:
            latest[fy] = (q, label)
    kept_labels = {label for _, label in latest.values()}
    kept = {label: quarters[label] for label in kept_labels}
    superseded = {
        label: latest[_QUARTER_LABEL.match(label).group(1)][1]
        for label in quarters
        if label not in kept_labels
    }
    return kept, superseded


def build_sponsor_table(soc_codes, wage_level, quarters):
    """Aggregate certified `wage_level` filings for `soc_codes` into one row
    per normalized employer.

    quarters: {label: DataFrame} as returned by load_quarters(). Cumulative
    same-FY quarters are collapsed to the latest file first (see
    supersede_cumulative_quarters).
    Returns (table, stats): the sponsor table sorted by quarters_present then
    filing_count (both descending), and a stats dict used for verification
    and provenance.
    """
    quarters, superseded = supersede_cumulative_quarters(quarters)
    frames = []
    for label in sorted(quarters):
        frame = quarters[label].copy()
        frame["QUARTER"] = label
        frames.append(frame)
    rows = pd.concat(frames, ignore_index=True)

    stats = {
        "quarters": sorted(quarters),
        "quarters_superseded": superseded,
        "rows_per_quarter": {label: int(len(quarters[label])) for label in sorted(quarters)},
        "rows_total": int(len(rows)),
    }

    status = _clean(rows["CASE_STATUS"]).str.upper()
    stats["case_statuses_seen"] = dict(Counter(status).most_common(10))
    certified = rows[status == "CERTIFIED"]
    stats["rows_certified"] = int(len(certified))
    if certified.empty:
        raise RunwayError(
            "No rows have CASE_STATUS = Certified.\n"
            f"Statuses in this data: {_top_values(rows['CASE_STATUS'])}.\n"
            "Is this the right disclosure file?"
        )

    soc = _clean(certified["SOC_CODE"]).map(normalize_soc)
    matched = certified[soc.isin(set(soc_codes))]
    stats["rows_soc_matched"] = int(len(matched))
    if matched.empty:
        raise RunwayError(
            f"No certified rows matched the SOC codes {sorted(soc_codes)}.\n"
            f"Most common SOC codes in this data: {_top_values(certified['SOC_CODE'])}.\n"
            "Is this an LCA disclosure file for the expected period?"
        )

    stats["wage_levels_seen"] = dict(Counter(_clean(matched["PW_WAGE_LEVEL"])).most_common(10))
    levels = matched["PW_WAGE_LEVEL"].map(normalize_wage_level)
    selected = matched[levels == wage_level].copy()
    stats["rows_selected"] = int(len(selected))
    if selected.empty:
        raise RunwayError(
            f"No matched rows at prevailing-wage level {wage_level}.\n"
            f"PW_WAGE_LEVEL values in this data: {_top_values(matched['PW_WAGE_LEVEL'])}.\n"
            "If DOL introduced a new spelling, normalize_wage_level() needs to learn it."
        )

    wage_from = pd.to_numeric(
        _clean(selected["WAGE_RATE_OF_PAY_FROM"]).str.replace(r"[$,]", "", regex=True),
        errors="coerce",
    )
    unit = _clean(selected["WAGE_UNIT_OF_PAY"]).str.upper()
    selected["_wage_annual"] = wage_from * unit.map(WAGE_UNIT_TO_ANNUAL)
    stats["wage_units_seen"] = dict(Counter(unit).most_common(10))
    stats["rows_wage_excluded"] = int(selected["_wage_annual"].isna().sum())

    raw_names = _clean(selected["EMPLOYER_NAME"])
    selected["_employer_key"] = raw_names.map(normalize_employer)
    stats["distinct_raw_employers"] = int(raw_names.nunique())

    records = []
    for key, group in selected.groupby("_employer_key"):
        name_counts = Counter(_clean(group["EMPLOYER_NAME"]))
        display = sorted(name_counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        quarter_list = sorted(group["QUARTER"].unique())
        wages = group["_wage_annual"].dropna()
        records.append({
            "employer": key,
            "employer_display": display,
            "filing_count": int(len(group)),
            "quarters_present": len(quarter_list),
            "quarters": "; ".join(quarter_list),
            "repeat_sponsor": "yes" if len(quarter_list) >= 2 else "no",
            "soc_codes": "; ".join(sorted({normalize_soc(c) for c in group["SOC_CODE"]})),
            "soc_titles": _distinct_joined(group["SOC_TITLE"]),
            "worksite_states": _distinct_joined(group["WORKSITE_STATE"].astype(str).str.upper()),
            "worksite_cities": _distinct_joined(group["WORKSITE_CITY"]),
            "wage_annual_min": round(wages.min()) if len(wages) else None,
            "wage_annual_median": round(wages.median()) if len(wages) else None,
            "wage_annual_max": round(wages.max()) if len(wages) else None,
        })
    table = (
        pd.DataFrame(records)
        .sort_values(
            ["quarters_present", "filing_count", "employer"],
            ascending=[False, False, True],
        )
        .reset_index(drop=True)
    )
    stats["employer_groups"] = int(len(table))
    return table, stats
