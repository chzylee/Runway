"""Shared test plumbing (v1).

Two worlds:

* Unit/property tests import the engine in-process. `sys.path` is set so
  `import engine...`, `import build_shortlist`, `import _util` resolve exactly as
  they do when a script runs.

* Emit-integration tests exercise the REAL data path (convert -> shortlist ->
  emit web/data/) against the committed synthetic fixture in a throwaway tmp dir,
  via the `emit_env` fixture, so every read and write is isolated from the
  developer's real data/ and web/ trees.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("PYTHONUTF8", "1")

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"

# Resolve engine + scripts imports the way the scripts themselves do.
for _p in (str(REPO_ROOT), str(SCRIPTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from engine.sponsors import REQUIRED_COLUMNS  # noqa: E402

# A row that passes every filter; individual tests override only what they test.
_GOOD_ROW = {
    "CASE_STATUS": "Certified",
    "VISA_CLASS": "H-1B",
    "JOB_TITLE": "Designer",
    "SOC_CODE": "15-1255.00",
    "SOC_TITLE": "Web and Digital Interface Designers",
    "EMPLOYER_NAME": "Acme Design LLC",
    "WORKSITE_CITY": "Austin",
    "WORKSITE_STATE": "TX",
    "WAGE_RATE_OF_PAY_FROM": "85000",
    "WAGE_RATE_OF_PAY_TO": "95000",
    "WAGE_UNIT_OF_PAY": "Year",
    "PW_WAGE_LEVEL": "I",
}


def make_frame(rows):
    """Build a DOL-shaped in-memory frame from partial row dicts. Every row
    starts from a selectable baseline, so a test states only the fields under
    test and trusts the rest to pass the funnel."""
    full = [{**_GOOD_ROW, **r} for r in rows]
    return pd.DataFrame(full, columns=REQUIRED_COLUMNS).astype("string")


@pytest.fixture
def frame():
    """The synthetic-frame builder, as a fixture."""
    return make_frame


@pytest.fixture
def emit_env(tmp_path, monkeypatch):
    """Run the REAL convert -> shortlist -> emit path against a tmp mini-repo.

    Redirects convert_quarters' and build_shortlist's path constants (and
    _util.REPO_ROOT for its relative_to prints) into tmp, so a test can drop the
    committed fixture xlsx, run the pipeline in-process, and read the three
    web/data/ artifacts the emit writes."""
    import convert_quarters
    import build_shortlist
    import _util

    raw = tmp_path / "data" / "raw"
    processed = tmp_path / "data" / "processed"
    webdata = tmp_path / "web" / "data"
    for directory in (raw, processed, webdata):
        directory.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(convert_quarters, "DATA_RAW", raw)
    monkeypatch.setattr(convert_quarters, "DATA_PROCESSED", processed)
    monkeypatch.setattr(convert_quarters, "ensure_dirs", lambda: None)
    monkeypatch.setattr(build_shortlist, "DATA_PROCESSED", processed)
    monkeypatch.setattr(build_shortlist, "WEB_DATA", webdata)
    monkeypatch.setattr(build_shortlist, "ensure_dirs", lambda: None)
    monkeypatch.setattr(_util, "REPO_ROOT", tmp_path)

    def place_fixture(src: Path):
        shutil.copy(src, raw / src.name)

    def run(requested_quarters=None):
        """convert every xlsx in raw, then emit; returns (table, stats)."""
        convert_quarters.convert_all()
        return build_shortlist.build(requested_quarters=requested_quarters)

    return SimpleNamespace(
        raw=raw, processed=processed, webdata=webdata,
        json=webdata / "design.json",
        provenance=webdata / "design.provenance.json",
        csv=webdata / "design.csv",
        place_fixture=place_fixture, run=run,
    )
