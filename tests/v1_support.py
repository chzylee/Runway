"""Shared plumbing for the fetch_quarters.py tests.

fetch_quarters.py owns I/O against the network and data/processed. It is not safe
to run against the developer's real data/, and the suite must never touch the
network (ratified SK-v1-1: the real fetch is proven by the first scheduled CI run,
Scenario C, not by the suite). So every test runs the real functions in-process
with their path constants and their network seam monkeypatched to a throwaway tmp
dir + a fake prober.

`fetch_env` redirects fetch_quarters' DATA_RAW/DATA_PROCESSED, pins the clock
(current_fiscal_year), and installs a fake HEAD-prober + a recording _download so
no socket is opened. `touch_parquet` writes an empty file with the exact name the
engine's discover_quarters() regex expects (lca_fy<YYYY>q<N>.parquet) - fetch tests
read only the *label* off the filename, never the parquet's bytes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

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
    a 404/503/429/timeout - which is the whole point of the P4/B prune-safety case.
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

    fy_now          - what current_fiscal_year() returns (pins the lookback window).
    published       - set of (fy, q) the fake HEAD-prober reports as 200.
    download_creates- if True, the recording _download also writes the dest xlsx
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
