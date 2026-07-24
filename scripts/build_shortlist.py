"""Build the public web/data/ artifacts for each registered role (engine.ROLE_SOC)
from converted quarters.

Runs the engine over every quarter found in data/processed/, verifies the result
(a failed check stops the run), and emits, per role, the three committed site
artifacts the frontend consumes (Design Doc §4.2, §7, D9; dec. #39 for the
per-role generalization):

  web/data/<role>/<role>.json             the closed §4.2 schema the site fetch()es
  web/data/<role>/<role>.provenance.json  the full audit/provenance object
  web/data/<role>/<role>.csv              the public shortlist download (v0 CSV columns)

All three (per role) are written in ONE job (#10 — the build identity is the
CSV<->provenance binding), guarded by a same-generation assertion (§4.3). The
emit only SERIALIZES what the engine already returned; it never recomputes the
shortlist.
"""
import argparse
import json
from datetime import datetime, timezone

import pandas as pd

import _util
from _util import CAVEATS, DATA_PROCESSED, WEB_DATA, ensure_dirs, run_cli

from engine import RunwayError
from engine.sponsors import ROLE_SOC, build_sponsor_table, load_quarters
from engine.verify import run_all

ROLE = "design"        # default role for a plain build() call — kept for callers/tests
                        # that only care about the one role they name.
WAGE_LEVEL = "I"


def _role_paths(role):
    role_dir = WEB_DATA / role
    return (role_dir / f"{role}.json", role_dir / f"{role}.provenance.json", role_dir / f"{role}.csv")

# The employer row columns, in order — exactly the v0 CSV columns (Design Doc §4.2
# employers[] = "exactly the v0 CSV columns"). Kept explicit so the closed schema is
# a stated contract, not whatever the DataFrame happens to carry.
EMPLOYER_COLUMNS = [
    "employer", "employer_display", "filing_count", "quarters_present", "quarters",
    "repeat_sponsor", "soc_codes", "soc_titles", "worksite_states", "worksite_cities",
    "wage_annual_min", "wage_annual_median", "wage_annual_max",
]
_INT_COLUMNS = {"filing_count", "quarters_present"}
_WAGE_COLUMNS = {"wage_annual_min", "wage_annual_median", "wage_annual_max"}


def _employer_records(table):
    """Serialize the shortlist table into JSON-safe records: ints are ints, a
    wage excluded from stats is JSON null (never the literal "nan" - the v0 F5
    lesson carried into the JSON emitter), text is a string (never NaN)."""
    records = []
    for _, row in table.iterrows():
        record = {}
        for column in EMPLOYER_COLUMNS:
            value = row[column]
            if column in _WAGE_COLUMNS:
                record[column] = None if pd.isna(value) else int(value)
            elif column in _INT_COLUMNS:
                record[column] = int(value)
            else:
                record[column] = "" if pd.isna(value) else str(value)
        records.append(record)
    return records


def build(role=ROLE, requested_quarters=None):
    ensure_dirs()
    json_path, provenance_path, csv_path = _role_paths(role)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    quarters = load_quarters(DATA_PROCESSED, requested_quarters)
    print(f"[shortlist:{role}] quarters loaded: {', '.join(sorted(quarters))}")

    table, stats = build_sponsor_table(ROLE_SOC[role], WAGE_LEVEL, quarters)
    for dropped, kept in sorted(stats["quarters_superseded"].items()):
        print(f"[shortlist:{role}] {dropped} superseded by cumulative {kept} (same fiscal year; "
              "DOL files are FYTD) - using the latest to avoid double-counting")
    for check in run_all(table, stats, quarters):
        print(f"[verify:{role}] {check.status:4} {check.name} - {check.detail}")

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    source = "US DOL OFLC LCA Programs disclosure data (public record)"

    employers = _employer_records(table)

    provenance = {
        "generated_at_utc": generated_at,
        "source": source,
        "filters": {
            "case_status": "Certified",
            "role": role,
            "soc_codes": ROLE_SOC[role],
            "pw_wage_level": WAGE_LEVEL,
        },
        "quarters_used": stats["quarters"],
        "quarters_superseded": stats["quarters_superseded"],
        "rows_per_quarter": stats["rows_per_quarter"],
        "funnel": {
            "rows_total": stats["rows_total"],
            "rows_certified": stats["rows_certified"],
            "rows_soc_matched": stats["rows_soc_matched"],
            "rows_selected": stats["rows_selected"],
        },
        "employer_groups": stats["employer_groups"],
        "distinct_raw_employer_spellings": stats["distinct_raw_employers"],
        "rows_wage_excluded_from_wage_stats": stats["rows_wage_excluded"],
        "case_statuses_seen": stats["case_statuses_seen"],
        "wage_levels_seen": stats["wage_levels_seen"],
        "wage_units_seen": stats["wage_units_seen"],
        "patterns": stats["patterns"],
        "caveats": CAVEATS,
    }

    # Same-generation guard (§4.3, the v0 F7 successor moved into the emit): the four
    # independently-sourced employer counts - the serialized rows, the engine stat, the
    # provenance object, and the pattern basis (dec. #44) - must agree, or we would ship
    # a stale JSON/provenance mix or patterns computed off a different generation.
    patterns_basis = stats["patterns"]["basis"]["employers"]
    if not (len(employers) == stats["employer_groups"]
            == provenance["employer_groups"] == patterns_basis):
        raise RunwayError(
            "Same-generation guard failed: employers rows="
            f"{len(employers)}, stats.employer_groups={stats['employer_groups']}, "
            f"provenance.employer_groups={provenance['employer_groups']}, "
            f"patterns.basis.employers={patterns_basis} disagree. "
            "Refusing to write a stale JSON/provenance mix."
        )

    site_data = {
        "role": role,
        "generated_at_utc": generated_at,
        "source": source,
        "filters": {
            "case_status": "Certified",
            "soc_codes": ROLE_SOC[role],
            "pw_wage_level": WAGE_LEVEL,
        },
        "quarters_used": stats["quarters"],
        "quarters_superseded": stats["quarters_superseded"],
        "funnel": {
            "rows_total": stats["rows_total"],
            "rows_certified": stats["rows_certified"],
            "rows_soc_matched": stats["rows_soc_matched"],
            "rows_selected": stats["rows_selected"],
        },
        "employer_groups": stats["employer_groups"],
        "rows_wage_excluded_from_wage_stats": stats["rows_wage_excluded"],
        "patterns": stats["patterns"],
        "caveats": CAVEATS,
        "employers": employers,
    }

    # All three written in one job (#10): the CSV is the v0 public download, provenance
    # the audit token, <role>.json the site's single fetch.
    table.to_csv(csv_path, index=False, encoding="utf-8", lineterminator="\n")
    provenance_path.write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
    json_path.write_text(json.dumps(site_data, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")

    print(
        f"[shortlist:{role}] {stats['employer_groups']} employers / {stats['rows_selected']} filings "
        f"-> {json_path.relative_to(_util.REPO_ROOT)} (+ .provenance.json, .csv)"
    )
    return table, stats


def build_all(requested_quarters=None):
    """Build every registered role's site artifacts (engine.ROLE_SOC is the registry —
    adding a role there is enough for it to show up here, dec. #3/#39)."""
    return {role: build(role=role, requested_quarters=requested_quarters) for role in ROLE_SOC}


def main():
    parser = argparse.ArgumentParser(description="Build the Level-I sponsor shortlists for every registered role.")
    parser.add_argument(
        "--quarters",
        help="comma-separated quarters you expect, e.g. FY2025Q4,FY2026Q1; the run stops with "
             "instructions if one has no converted data. Every converted quarter is always used.",
    )
    args = parser.parse_args()
    requested = [q for q in (args.quarters or "").split(",") if q.strip()] or None
    build_all(requested_quarters=requested)


if __name__ == "__main__":
    run_cli(main)
