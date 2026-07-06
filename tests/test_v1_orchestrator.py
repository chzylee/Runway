"""v1 slice — the CI gating orchestrator (scripts/run_pipeline.py).

Traces to TEST_SPEC.md §"v1 — Data-pipeline slice" P14 and P19, and
docs/decision_log.md dec. #28 (call E) + the dec.#22 push-retry (call K).

dec. #28 ratified that the convert/commit/push DECISIONS move out of the YAML
`if:` expressions (untestable) into a `scripts/run_pipeline.py` orchestrator that
pytest can drive with fabricated flags. That module does not exist yet, so both
tests are ⚠ red-first (xfail-strict, dec. #20 pattern): the import fails today and
each drives the extraction to green.

The imports are INSIDE the test bodies on purpose — a module-level `import
run_pipeline` would turn the missing module into a collection error (red command)
instead of a clean expected-failure.
"""
from __future__ import annotations

import importlib

import pytest


# ======================================================================== P14 ⚠
def test_P14_orchestrator_gates_convert_and_commit(monkeypatch):
    """P14/E (dec. #28): the gating decisions are unit-testable Python —
      * convert runs ONLY when fetch reported changed;
      * commit runs when fetch OR build reported changed.
    Driven with fabricated flags, no GitHub Actions needed."""
    run_pipeline = importlib.import_module("run_pipeline")

    assert run_pipeline.should_convert(fetch_changed=True) is True
    assert run_pipeline.should_convert(fetch_changed=False) is False

    assert run_pipeline.should_commit(fetch_changed=True, build_changed=False) is True
    assert run_pipeline.should_commit(fetch_changed=False, build_changed=True) is True
    assert run_pipeline.should_commit(fetch_changed=False, build_changed=False) is False


# ======================================================================== P19 ⚠
@pytest.mark.xfail(
    reason="P19/K — DEFERRED to v1.1 (dec. #32), marker kept. The `git push` step has no "
           "rebase-or-retry recovery, so a non-fast-forward would discard a run's regenerated "
           "data (push_with_retry + NonFastForward not built). Deferred: the concurrency group "
           "serializes runs and the worst case is a ~week wait to the next run, no data loss. "
           "The run_pipeline.py orchestrator seam (dec. #28) now exists for it to land into.",
    strict=True,
)
def test_P19_push_retry_rebases_on_non_fast_forward(monkeypatch):
    """P19/K (dec. #22): a non-fast-forward push must rebase and retry, never silently
    discard the run's regenerated parquet + shortlists. Driven with an injected push
    that is rejected once, then succeeds — the orchestrator must rebase between."""
    run_pipeline = importlib.import_module("run_pipeline")

    events = []

    def flaky_push():
        events.append("push")
        if events.count("push") == 1:
            raise run_pipeline.NonFastForward("remote moved")   # first attempt rejected

    def rebase():
        events.append("rebase")

    run_pipeline.push_with_retry(push=flaky_push, rebase=rebase)
    assert events == ["push", "rebase", "push"]                 # rebased, then retried
