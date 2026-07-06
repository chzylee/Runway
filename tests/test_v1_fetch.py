"""v1 slice — fetch_quarters.py: discovery, download reconcile, conservative prune.

Traces to TEST_SPEC.md §"v1 — Data-pipeline slice" (P1-P7, P11, P18, P20; Q1, Q3,
Q4) and docs/decision_log.md dec. #22/#27. The network is mocked throughout
(ratified SK-v1-1: the real fetch is Scenario C, the first scheduled CI run, never
the suite).

⚠ red-first (xfail-strict, dec. #20 pattern): P4 and Q3 pin the conservative-prune
contract the code does not yet honor (dec. #27 "currently red"); P20 pins the
label-collision guard (call J, "fix over note"). Each must FAIL against today's
code before its fix lands — an xfail that passes untouched means the test is wrong
(TEST_SPEC §v1.7).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from hypothesis import given, strategies as st

import fetch_quarters
from engine import RunwayError
from engine.sponsors import discover_quarters, supersede_cumulative_quarters
from v1_support import (
    fetch_env,
    make_prober,
    touch_parquet,
    url_for,
)

UTC = timezone.utc


# =========================================================================== P1
def test_P1_current_fiscal_year_boundary_is_total_fn_of_injected_date():
    """P1 (dec. #22; fetch_quarters.py:53): FY N runs Oct 1 (N-1) -> Sep 30 (N);
    Oct 1 flips to FY N+1 (Q1). A total function of the injected date — no reliance
    on the wall clock."""
    cfy = fetch_quarters.current_fiscal_year
    assert cfy(datetime(2099, 9, 30, tzinfo=UTC)) == 2099   # last day of FY2099
    assert cfy(datetime(2099, 10, 1, tzinfo=UTC)) == 2100   # FY2100 Q1 begins
    assert cfy(datetime(2099, 12, 31, tzinfo=UTC)) == 2100
    assert cfy(datetime(2100, 1, 1, tzinfo=UTC)) == 2100
    assert cfy(datetime(2100, 9, 30, tzinfo=UTC)) == 2100


# =========================================================================== Q1
@given(st.datetimes(min_value=datetime(1990, 1, 1), max_value=datetime(2200, 12, 31)))
def test_Q1_current_fiscal_year_total_and_deterministic(dt):
    """Q1 (invariant, anchors P1): current_fiscal_year is total (any date -> an int)
    and deterministic (same date -> same FY), and monotone across the Oct 1 boundary."""
    dt = dt.replace(tzinfo=UTC)
    fy = fetch_quarters.current_fiscal_year(dt)
    assert isinstance(fy, int)
    assert fy == (dt.year + 1 if dt.month >= 10 else dt.year)
    assert fetch_quarters.current_fiscal_year(dt) == fy


# =========================================================================== P2
def test_P2_discover_upstream_takes_highest_published_quarter_and_records_url(monkeypatch):
    """P2 (dec. #22; :79): per fiscal year, probe newest-first and take the highest
    PUBLISHED quarter (the cumulative FYTD file), recording its direct URL."""
    # Q3 and Q1 are both published; the cumulative Q3 must win, Q1 ignored.
    monkeypatch.setattr(fetch_quarters, "quarter_is_published",
                        make_prober({(2100, 3), (2100, 1)}))
    latest = fetch_quarters.discover_upstream([2100])
    assert set(latest) == {"FY2100Q3"}          # highest published, not Q1
    fy, q, url = latest["FY2100Q3"]
    assert (fy, q) == (2100, 3)
    assert url == url_for(2100, 3)               # the URL is recorded


# =========================================================================== P3
def test_P3_downloads_published_not_in_have_changed_true(tmp_path, monkeypatch):
    """P3 (dec. #22; :124): a published quarter not already committed as parquet is
    downloaded, and fetch reports changed=True."""
    env = fetch_env(tmp_path, monkeypatch, fy_now=2100, published={(2100, 1), (2099, 1)})
    changed = fetch_quarters.fetch()
    assert changed is True
    assert sorted(p.name for p in env.downloads) == [
        "LCA_Disclosure_Data_FY2099_Q1.xlsx",
        "LCA_Disclosure_Data_FY2100_Q1.xlsx",
    ]


def test_P3_skips_quarters_already_in_have_changed_false(tmp_path, monkeypatch):
    """P3 (dec. #22; :124): a published quarter already committed is skipped; with
    nothing to download or prune, changed=False (disk unchanged)."""
    env = fetch_env(tmp_path, monkeypatch, fy_now=2100, published={(2100, 1), (2099, 1)})
    touch_parquet(env.processed, "FY2100Q1")
    touch_parquet(env.processed, "FY2099Q1")
    changed = fetch_quarters.fetch()
    assert changed is False
    assert env.downloads == []


# ======================================================================== P4 ⚠
@pytest.mark.xfail(
    reason="dec.#27 (call B): fetch prunes any committed quarter absent from this "
           "run's upstream set (fetch_quarters.py:161), so a transient probe-miss on "
           "one in-window FY deletes valid committed parquet. Red-first — drive to green.",
    strict=True,
)
def test_P4_probe_miss_on_in_window_fy_never_prunes(tmp_path, monkeypatch):
    """P4/B (dec. #27; :161): committed {FY2099Q1, FY2100Q1}; a run where FY2100Q1
    resolves (200) but every FY2099 probe misses (a 503/timeout). FY2099 is still
    in-window and no newer same-FY quarter was positively observed, so its parquet
    MUST survive — the ≥2-fiscal-year repeat-sponsor floor depends on it."""
    env = fetch_env(tmp_path, monkeypatch, fy_now=2100, published={(2100, 1)})
    survivor = touch_parquet(env.processed, "FY2099Q1")   # in-window, probe missed
    touch_parquet(env.processed, "FY2100Q1")              # still published
    fetch_quarters.fetch()                                # upstream non-empty -> no blackout
    assert survivor.exists(), "an in-window FY with a transient probe-miss must not be pruned"


# ======================================================================== Q3 ⚠
@pytest.mark.xfail(
    reason="dec.#27 (Q3/B): quarter_is_published collapses ANY non-200 (404/503/429/"
           "timeout) to a probe-miss, and the broad prune then deletes committed "
           "in-window parquet. Red-first.",
    strict=True,
)
@pytest.mark.parametrize("transient", ["404-not-found", "503-service-unavailable", "429-rate-limited"])
def test_Q3_prune_safety_across_transient_statuses(tmp_path, monkeypatch, transient):
    """Q3 (invariant, anchors P4/B): a committed in-window FY parquet is removed ONLY
    on supersession or out-of-window — never because a probe returned a transient
    non-200. The fake prober models all of 404/5xx/429 as the same 'not published'
    signal the real code produces."""
    env = fetch_env(tmp_path, monkeypatch, fy_now=2100, published={(2100, 1)})
    survivor = touch_parquet(env.processed, "FY2099Q1")
    touch_parquet(env.processed, "FY2100Q1")
    fetch_quarters.fetch()
    assert survivor.exists(), f"{transient}: an in-window FY must survive a probe-miss"


# =========================================================================== P5
def test_P5_total_blackout_raises_naming_readme_and_prunes_nothing(tmp_path, monkeypatch):
    """P5 (dec. #22/#23; :138): when NO fiscal year publishes anything, fetch stops
    with a RunwayError naming the README URL template — and prunes nothing (the raise
    happens before the prune loop, so committed data survives a total blackout)."""
    env = fetch_env(tmp_path, monkeypatch, fy_now=2100, published=set())
    committed = touch_parquet(env.processed, "FY2099Q1")
    with pytest.raises(RunwayError) as excinfo:
        fetch_quarters.fetch()
    message = str(excinfo.value)
    assert "README" in message and "URL template" in message
    assert committed.exists()                    # prunes nothing on blackout


# =========================================================================== P6
def test_P6_network_error_raises_plain_english_naming_url_and_readme(monkeypatch):
    """P6 (dec. #15; :71): a URLError (host down / template moved) surfaces as a
    RunwayError whose message names the failing URL and points at README.md —
    self-diagnosing, never a raw traceback."""
    import urllib.error

    def boom(*args, **kwargs):
        raise urllib.error.URLError("host unreachable")

    monkeypatch.setattr("urllib.request.urlopen", boom)
    with pytest.raises(RunwayError) as excinfo:
        fetch_quarters.quarter_is_published(2100, 1)
    message = str(excinfo.value)
    assert url_for(2100, 1) in message
    assert "README" in message


# =========================================================================== P7
def test_P7_fetch_emits_changed_to_github_output(tmp_path, monkeypatch):
    """P7 (dec. #22/#24; :172): under GitHub Actions, fetch writes changed=true|false
    to $GITHUB_OUTPUT so the convert step can gate on it."""
    out = tmp_path / "gh_output.txt"
    out.write_text("", encoding="utf-8")
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    fetch_quarters._emit_github_output(True)
    fetch_quarters._emit_github_output(False)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert "changed=true" in lines
    assert "changed=false" in lines


# ========================================================== P11 + Q4 (fetch<->engine)
def test_P11_Q4_post_fetch_state_one_parquet_per_fy_supersede_empty(tmp_path, monkeypatch):
    """P11 (dec. #22 <-> #21) + Q4: the steady state fetch maintains is exactly one
    parquet per in-window fiscal year, so the engine's cumulative-FYTD supersession is
    a no-op on it (empty superseded map). fetch and engine agree at the seam."""
    env = fetch_env(tmp_path, monkeypatch, fy_now=2100, published={(2100, 1), (2099, 1)})
    a = touch_parquet(env.processed, "FY2100Q1")
    b = touch_parquet(env.processed, "FY2099Q1")
    changed = fetch_quarters.fetch()
    assert changed is False                      # already current
    assert a.exists() and b.exists()             # one-per-FY, nothing pruned
    kept, superseded = supersede_cumulative_quarters(discover_quarters(env.processed))
    assert superseded == {}                       # Q4: no same-FY collapse
    assert set(kept) == {"FY2100Q1", "FY2099Q1"}


# =========================================================================== P18
def test_P18_download_truncation_guard_raises_and_leaves_no_file(tmp_path, monkeypatch):
    """P18/D (dec. #7; :115): a Content-Length mismatch (a truncated stream) stops
    with a RunwayError and leaves NO file at dest (nor a .part temp).

    NOTE (finding): the spec's index marks P18 ⚠, but the guard is already implemented
    at fetch_quarters.py:115 (and ratification-log call D reads 'mock the Content-Length
    guard', i.e. test the existing behavior). So this is GREEN, not red-first — the
    ratification-log red-first set is {A,B,C,E,G,H}. Reported for the assertion review."""
    dest = tmp_path / "LCA_Disclosure_Data_FY2100_Q1.xlsx"

    class FakeResponse:
        headers = {"Content-Length": "100"}      # claims 100 bytes...

        def __init__(self):
            self._chunks = [b"x" * 50]            # ...but only serves 50

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, size):
            return self._chunks.pop(0) if self._chunks else b""

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: FakeResponse())
    with pytest.raises(RunwayError) as excinfo:
        fetch_quarters._download(url_for(2100, 1), dest)
    assert "truncated" in str(excinfo.value).lower()
    assert not dest.exists()
    assert not dest.with_suffix(dest.suffix + ".part").exists()


# ======================================================================== P20 ⚠
@pytest.mark.xfail(
    reason="call J (fix over note): discover_quarters maps two case-only-different "
           "filenames to one FY label and silently keeps just one (dict overwrite, "
           "sponsors.py:101). A silent drop must become a deterministic tie-break or a "
           "hard error. Red-first (this test asserts the hard-error resolution).",
    strict=True,
)
def test_P20_discover_quarters_case_only_label_collision_no_silent_drop(tmp_path, monkeypatch):
    """P20/J (sponsors.py:101): on a case-insensitive-regex label collision — two
    parquet whose names differ only in case both map to FY2099Q1 — the function must
    NOT silently return one and drop the other. (Windows coalesces such names on disk,
    so the collision is injected through the glob seam to stay cross-platform.)"""
    from pathlib import Path

    real_glob = Path.glob
    collided = [Path("lca_fy2099q1.parquet"), Path("LCA_FY2099Q1.parquet")]

    def fake_glob(self, pattern):
        if self == tmp_path:
            return iter(collided)
        return real_glob(self, pattern)

    monkeypatch.setattr(Path, "glob", fake_glob)
    with pytest.raises(RunwayError):
        discover_quarters(tmp_path)
