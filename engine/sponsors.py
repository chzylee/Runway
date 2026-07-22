"""Deterministic sponsor engine over converted DOL LCA disclosure quarters.

Reads narrow parquet files from data/processed/, filters to certified
entry-wage filings for a role's SOC codes, and aggregates one row per
normalized employer. Pure data in, data out - no LLM, no HTML, no printing.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
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
    # Added dec. #44 for the title-shortlist pattern block: NAICS_CODE (employer's
    # self-reported industry) and SECONDARY_ENTITY (worker at a third-party site ->
    # agency/staffing vs in-house). Both are read-only pattern inputs; neither
    # touches the certified/SOC/wage-level filter or the employer aggregation.
    "NAICS_CODE",
    "SECONDARY_ENTITY",
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


# --------------------------------------------------------------------------- #
# Title-shortlist patterns (dec. #44)
#
# Deterministic, employer-denominated aggregates over the SELECTED rows (the
# certified Level-I filings for a role) — the "title-shortlist." Counts only, no
# interpretation: the reasoning happens later in the user's own LLM, off these
# facts. Every count carries BOTH denominators (employers and filings); a token
# or industry below the employer support floor is omitted entirely, never hedged.
# The employer denominator (not filings) is deliberate: one prolific filer must
# not be able to manufacture a pattern.
# --------------------------------------------------------------------------- #

# No pattern (a recurring token or an industry) is stated unless at least this
# many DISTINCT employers back it. At real Level-I design volumes (~30 employers)
# this is ~10%. Widen/narrow if a real pull looks too sparse or too noisy.
PATTERN_MIN_SUPPORT = 3

# Title tokens stripped before counting recurrences (dec. #44, ratified knob 3).
# We strip ONLY words that cannot discriminate *within* the title-shortlist:
#   - the role-family filter words (design/designer(s)) — true of ~100% of rows
#     by construction, since every selected row matched a design SOC code, so
#     they carry zero signal here (not an arbitrary blocklist); and
#   - lexically empty words (articles/conjunctions/prepositions) and bare
#     numerals / roman level markers.
# Everything else survives — crucially seniority (senior/junior/lead/founding/
# associate) and domain/function words (product/web/graphic/ux/research), which
# are the actual signal. Adding a NON-design role family later revisits the
# role-word set (the clean "add a title" path noted alongside knob 2).
_TITLE_ROLE_STOPWORDS = {"design", "designer", "designers"}
_TITLE_GENERIC_STOPWORDS = {
    "a", "an", "the", "of", "and", "for", "to", "in", "on", "with", "at", "by", "or",
}
_TITLE_ROMAN_TOKENS = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}
_ALL_DIGITS = re.compile(r"^\d+$")

# Official Census NAICS 2-digit sector titles (a fixed government list, not a
# judgment). Sectors that span a range share a label (Manufacturing 31-33, Retail
# 44-45, Transportation 48-49), so each prefix maps to the same sector name.
NAICS2_SECTORS = {
    "11": "Agriculture, Forestry, Fishing and Hunting",
    "21": "Mining, Quarrying, and Oil and Gas Extraction",
    "22": "Utilities",
    "23": "Construction",
    "31": "Manufacturing", "32": "Manufacturing", "33": "Manufacturing",
    "42": "Wholesale Trade",
    "44": "Retail Trade", "45": "Retail Trade",
    "48": "Transportation and Warehousing", "49": "Transportation and Warehousing",
    "51": "Information",
    "52": "Finance and Insurance",
    "53": "Real Estate and Rental and Leasing",
    "54": "Professional, Scientific, and Technical Services",
    "55": "Management of Companies and Enterprises",
    "56": "Administrative and Support and Waste Management and Remediation Services",
    "61": "Educational Services",
    "62": "Health Care and Social Assistance",
    "71": "Arts, Entertainment, and Recreation",
    "72": "Accommodation and Food Services",
    "81": "Other Services (except Public Administration)",
    "92": "Public Administration",
}


def title_tokens(title: str) -> set[str]:
    """The discriminating word tokens in one job title (see stopword rationale
    above). Returns a SET so a token counts once per filing, never inflated by a
    title that repeats a word."""
    tokens = set()
    for word in re.split(r"[^a-z0-9]+", str(title).lower()):
        if len(word) < 2:                       # drop "" and stray single chars
            continue
        if word in _TITLE_ROLE_STOPWORDS or word in _TITLE_GENERIC_STOPWORDS:
            continue
        if word in _TITLE_ROMAN_TOKENS or _ALL_DIGITS.match(word):
            continue
        tokens.add(word)
    return tokens


def canonical_onet(raw) -> str:
    """Canonical O*NET detail code, PRESERVING the decimal suffix that
    normalize_soc() strips for matching. Bare base "15-1255" is the ".00" base
    occupation; "15-1255.01" (Video Game Designers) stays distinct. This only
    REPORTS composition — it never changes what the SOC filter matches (dec. #39)."""
    s = str(raw).strip()
    if not s:
        return ""
    base, dot, detail = s.partition(".")
    if not dot or detail == "" or detail == "0":
        detail = "00"
    return f"{base}.{detail}"


def _bucket_counts(keys_by_bucket, filings_by_bucket):
    """{bucket: set_of_employer_keys} + {bucket: filing_count} -> sorted records
    of {..., employers, filings}, employers-desc then filings-desc."""
    records = []
    for bucket, emps in keys_by_bucket.items():
        records.append((bucket, len(emps), int(filings_by_bucket[bucket])))
    return records


def compute_patterns(selected, min_support_employers=PATTERN_MIN_SUPPORT):
    """Employer-denominated pattern aggregates over the selected title-shortlist
    rows. `selected` must already carry the `_employer_key` column that
    build_sponsor_table assigns. Pure counting; returns the JSON-ready patterns
    object (dec. #44)."""
    keys = list(selected["_employer_key"])
    n_employers = len(set(keys))
    n_filings = len(selected)

    # --- job-title tokens (floor-gated pattern) ---
    titles = list(_clean(selected["JOB_TITLE"]))
    token_employers = defaultdict(set)
    token_filings = Counter()
    for title, key in zip(titles, keys):
        for tok in title_tokens(title):
            token_employers[tok].add(key)
            token_filings[tok] += 1
    recurring_tokens = [
        {"token": tok, "employers": len(emps), "filings": int(token_filings[tok])}
        for tok, emps in token_employers.items()
        if len(emps) >= min_support_employers
    ]
    recurring_tokens.sort(key=lambda d: (-d["employers"], -d["filings"], d["token"]))

    # --- distinct titles (verbatim evidence: no stopword, no floor) ---
    title_employers = defaultdict(set)
    title_filings = Counter()
    for title, key in zip(titles, keys):
        label = title if title else "(blank)"
        title_employers[label].add(key)
        title_filings[label] += 1
    distinct_titles = [
        {"title": label, "employers": len(emps), "filings": int(title_filings[label])}
        for label, emps in title_employers.items()
    ]
    distinct_titles.sort(key=lambda d: (-d["employers"], -d["filings"], d["title"]))

    # --- O*NET occupation split (reporting only; suffix preserved) ---
    codes = [canonical_onet(c) for c in _clean(selected["SOC_CODE"])]
    soc_titles = list(_clean(selected["SOC_TITLE"]))
    onet_employers = defaultdict(set)
    onet_filings = Counter()
    onet_title_votes = defaultdict(Counter)
    for code, soc_title, key in zip(codes, soc_titles, keys):
        onet_employers[code].add(key)
        onet_filings[code] += 1
        if soc_title:
            onet_title_votes[code][soc_title] += 1
    onet_occupations = []
    for code, emps in onet_employers.items():
        votes = onet_title_votes[code]
        title = votes.most_common(1)[0][0] if votes else ""
        onet_occupations.append({
            "soc_code": code, "title": title,
            "employers": len(emps), "filings": int(onet_filings[code]),
        })
    onet_occupations.sort(key=lambda d: (-d["filings"], -d["employers"], d["soc_code"]))

    # --- placement model: in-house vs third-party worksite (SECONDARY_ENTITY) ---
    # Filings partition cleanly; an employer with filings of BOTH kinds is counted
    # in both employer buckets (the buckets are not employer-exclusive).
    secondary = _clean(selected["SECONDARY_ENTITY"]).str.upper()
    third_party = [s == "YES" for s in secondary]
    tp_keys = {k for k, is_tp in zip(keys, third_party) if is_tp}
    ih_keys = {k for k, is_tp in zip(keys, third_party) if not is_tp}
    placement_model = {
        "in_house": {"employers": len(ih_keys), "filings": sum(1 for x in third_party if not x)},
        "third_party_site": {"employers": len(tp_keys), "filings": sum(1 for x in third_party if x)},
    }

    # --- industry (NAICS 2-digit sector, floor-gated) ---
    naics2 = [c[:2] for c in _clean(selected["NAICS_CODE"])]
    naics_employers = defaultdict(set)
    naics_filings = Counter()
    for code, key in zip(naics2, keys):
        if not code:
            continue
        naics_employers[code].add(key)
        naics_filings[code] += 1
    industry_naics2 = [
        {"code": code, "label": NAICS2_SECTORS.get(code, "Other / Unclassified"),
         "employers": len(emps), "filings": int(naics_filings[code])}
        for code, emps in naics_employers.items()
        if len(emps) >= min_support_employers
    ]
    industry_naics2.sort(key=lambda d: (-d["employers"], -d["filings"], d["code"]))

    return {
        "basis": {
            "filings": int(n_filings),
            "employers": int(n_employers),
            "measured_by": "employers",
            "min_support_employers": int(min_support_employers),
        },
        "job_titles": {
            "recurring_tokens": recurring_tokens,
            "distinct_titles": distinct_titles,
        },
        "onet_occupations": onet_occupations,
        "placement_model": placement_model,
        "industry_naics2": industry_naics2,
    }


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

    # Title-shortlist patterns over the same selected rows (dec. #44). Computed
    # here so the emit only serializes; basis.employers is the same denominator
    # as employer_groups (the emit's same-generation guard pins that).
    stats["patterns"] = compute_patterns(selected)
    return table, stats
