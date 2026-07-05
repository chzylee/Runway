"""Shared test plumbing.

Two worlds live here:

* Unit/property tests import the engine (and, for report-side units, the
  scripts) in-process. `sys.path` is set so `import engine...`, `import
  build_report`, `import _util` resolve exactly as they do when a script runs.

* Fixture-integration tests exercise the REAL pipeline as a subprocess against
  a throwaway mini-repo (`pipeline_env`): a tmp dir holding copies of engine/
  and scripts/ so `_util.REPO_ROOT` resolves inside the tmp dir and every read
  and write is isolated from the developer's real data/ and output/.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

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


class PipelineEnv:
    """A throwaway mini-repo that runs the real scripts as a subprocess."""

    def __init__(self, root: Path):
        self.root = root
        self.raw = root / "data" / "raw"
        self.processed = root / "data" / "processed"
        self.output = root / "output"
        self.private = root / "output" / "private"
        for d in (self.raw, self.processed, self.private):
            d.mkdir(parents=True, exist_ok=True)
        # Copy the code under test so REPO_ROOT resolves inside this tmp dir.
        shutil.copytree(REPO_ROOT / "engine", root / "engine")
        shutil.copytree(SCRIPTS_DIR, root / "scripts")
        self.csv = self.output / "sponsors_levelI.csv"
        self.provenance = self.output / "sponsors_levelI.provenance.json"
        self.hiring_now = self.private / "hiring_now.csv"
        self.gap_read = self.private / "gap_read_filled.md"
        self.report = self.private / "runway_report.html"

    def place_fixture(self, src: Path, name: str | None = None):
        dest = self.raw / (name or src.name)
        shutil.copy(src, dest)
        return dest

    def run(self, script="run.py", *args, env=None, expect_ok=None):
        """Invoke `python <root>/scripts/<script>` and capture the result.
        Runs with UTF-8 forced off at the parent so force_utf8() is what makes
        the run survive a non-UTF-8 console (M15)."""
        full_env = dict(os.environ)
        full_env.pop("PYTHONUTF8", None)  # let the tool force it, not the parent
        if env:
            full_env.update(env)
        proc = subprocess.run(
            [sys.executable, str(self.root / "scripts" / script), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=self.root, env=full_env,
        )
        if expect_ok is True:
            assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}\n{proc.stderr}"
        if expect_ok is False:
            assert proc.returncode == 1, f"expected exit 1, got {proc.returncode}\n{proc.stdout}\n{proc.stderr}"
        return proc


@pytest.fixture
def pipeline_env(tmp_path):
    return PipelineEnv(tmp_path)


def assert_no_traceback(proc):
    """The RunwayError contract (dec. #15): anticipated failures print a plain
    message and exit 1 with no Python stack trace."""
    assert "Traceback (most recent call last)" not in proc.stderr, (
        f"a stack trace leaked to stderr:\n{proc.stderr}"
    )
