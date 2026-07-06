"""Shared plumbing for the v1 data-pipeline slice tests.

The v1 slice (TEST_SPEC.md §"v1 — Data-pipeline slice") exercises two scripts
that own I/O against the network and the committed repo:

  * scripts/fetch_quarters.py   — discover + download + prune DOL quarters
  * scripts/build_shortlists.py — per-title incremental shortlist build + manifest

Neither is safe to run against the developer's real data/ or output/, and the
suite must never touch the network (ratified SK-v1-1: the real fetch is proven by
the first scheduled CI run, Scenario C, not by the suite). So every test here runs
the real functions in-process with their path constants and their network seam
monkeypatched to a throwaway tmp dir + a fake prober.

Two harnesses:
  * `fetch_env`  — redirects fetch_quarters' DATA_RAW/DATA_PROCESSED, pins the
    clock (current_fiscal_year), and installs a fake HEAD-prober + a recording
    _download so no socket is opened.
  * `build_env`  — redirects build_shortlists' DATA_PROCESSED/SHORTLISTS_DIR/
    MANIFEST_PATH (and _util.REPO_ROOT for its relative_to prints) into tmp.

Fixtures are synthetic frames written to parquet with the exact name the engine's
discover_quarters() regex expects (lca_fy<YYYY>q<N>.parquet); for fetch tests that
only read the *label* off the filename, `touch_parquet` writes an empty file.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from conftest import make_frame

# The URL template fetch_quarters HEAD-probes (README.md / decision_log.md #22).
URL_TEMPLATE = (
    "https://www.dol.gov/sites/dolgov/files/ETA/oflc/pdfs/"
    "LCA_Disclosure_Data_FY{fy}_Q{q}.xlsx"
)


def url_for(fy, q):
    return URL_TEMPLATE.format(fy=fy, q=q)


def parquet_name(label):
    """"FY2099Q1" -> "lca_fy2099q1.parquet" (the name discover_quarters matches)."""
    fy = label[2:6]
    q = label[7]
    return f"lca_fy{fy}q{q}.parquet"


# Three selectable design filings across two employers, enough to exercise
# aggregation + wage stats so build_sponsor_table + verify.run_all pass cleanly.
_SELECTABLE_ROWS = [
    {"EMPLOYER_NAME": "Acme Design LLC", "SOC_CODE": "15-1255.00", "WAGE_RATE_OF_PAY_FROM": "85000"},
    {"EMPLOYER_NAME": "Acme Design LLC", "SOC_CODE": "15-1255.00", "WAGE_RATE_OF_PAY_FROM": "95000"},
    {"EMPLOYER_NAME": "Beta Studio LLC", "SOC_CODE": "27-1024", "WAGE_RATE_OF_PAY_FROM": "90000",
     "SOC_TITLE": "Graphic Designers"},
]


def write_selectable_parquet(processed_dir, label, rows=None):
    """Write a real, engine-readable parquet for `label` that selects rows for the
    default `design` role (so build_sponsor_table succeeds)."""
    processed_dir = Path(processed_dir)
    processed_dir.mkdir(parents=True, exist_ok=True)
    frame = make_frame(rows if rows is not None else _SELECTABLE_ROWS)
    path = processed_dir / parquet_name(label)
    frame.to_parquet(path, index=False)
    return path


def touch_parquet(processed_dir, label):
    """Write an empty file with a valid parquet name. Enough for fetch tests, which
    read only the quarter label off the filename (discover_quarters never opens it)."""
    processed_dir = Path(processed_dir)
    processed_dir.mkdir(parents=True, exist_ok=True)
    path = processed_dir / parquet_name(label)
    path.write_bytes(b"")
    return path


def make_prober(published):
    """A fake quarter_is_published: True iff (fy, q) is in `published`.

    A missing (fy, q) collapses to (False, url) exactly as the real prober does for
    a 404/503/429/timeout — which is the whole point of the P4/B prune-safety case.
    """
    published = set(published)

    def prober(fy, q):
        return ((fy, q) in published, url_for(fy, q))

    return prober


@dataclass
class FetchEnv:
    raw: Path
    processed: Path
    downloads: list = field(default_factory=list)


def fetch_env(tmp_path, monkeypatch, *, fy_now, published, download_creates=False):
    """Redirect fetch_quarters at tmp + install a fake prober. No network is used.

    fy_now          — what current_fiscal_year() returns (pins the lookback window).
    published       — set of (fy, q) the fake HEAD-prober reports as 200.
    download_creates— if True, the recording _download also writes the dest xlsx
                      (so a follow-up convert step could read it); default records only.
    """
    import fetch_quarters

    raw = tmp_path / "data" / "raw"
    processed = tmp_path / "data" / "processed"
    raw.mkdir(parents=True, exist_ok=True)
    processed.mkdir(parents=True, exist_ok=True)
    env = FetchEnv(raw=raw, processed=processed)

    monkeypatch.setattr(fetch_quarters, "DATA_RAW", raw)
    monkeypatch.setattr(fetch_quarters, "DATA_PROCESSED", processed)
    monkeypatch.setattr(fetch_quarters, "ensure_dirs", lambda: None)
    monkeypatch.setattr(fetch_quarters, "current_fiscal_year", lambda today=None: fy_now)
    monkeypatch.setattr(fetch_quarters, "quarter_is_published", make_prober(published))

    def fake_download(url, dest):
        env.downloads.append(Path(dest))
        if download_creates:
            Path(dest).write_bytes(b"xlsx-placeholder")

    monkeypatch.setattr(fetch_quarters, "_download", fake_download)
    return env


@dataclass
class BuildEnv:
    processed: Path
    shortlists: Path
    manifest_path: Path

    def read_manifest(self):
        import json
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def parquet(self, title):
        return self.shortlists / f"{title}_levelI.parquet"


def build_env(tmp_path, monkeypatch, *, role_soc=None):
    """Redirect build_shortlists' storage + manifest into tmp so build_all() runs
    against a throwaway repo. `role_soc` overrides engine.ROLE_SOC for the run
    (add/remove titles without touching the real registry)."""
    import build_shortlists
    import _util

    processed = tmp_path / "data" / "processed"
    shortlists = tmp_path / "output" / "shortlists"
    processed.mkdir(parents=True, exist_ok=True)
    shortlists.mkdir(parents=True, exist_ok=True)
    manifest_path = shortlists / "index.json"

    monkeypatch.setattr(build_shortlists, "DATA_PROCESSED", processed)
    monkeypatch.setattr(build_shortlists, "SHORTLISTS_DIR", shortlists)
    monkeypatch.setattr(build_shortlists, "MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(build_shortlists, "ensure_dirs", lambda: None)
    monkeypatch.setattr(_util, "REPO_ROOT", tmp_path)
    if role_soc is not None:
        monkeypatch.setattr(build_shortlists, "ROLE_SOC", role_soc)

    return BuildEnv(processed=processed, shortlists=shortlists, manifest_path=manifest_path)
