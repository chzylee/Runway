"""v1 Increment 2 — the caveats-parity build check (dec. #34, Design Doc §7/D5).

`prompts/recommendations.md` is the one tolerated second copy of `_util.CAVEATS`,
because the site fetches that template and shows its caveats to an applicant without
the strings ever passing through the engine. `scripts/check_caveats_parity.py` asserts
the two are byte-for-byte identical; this suite pins that behavior both ways:

* positive — the real committed repo files agree (guards actual drift in CI/the suite);
* negative — an injected drift, a non-caveat line, and a missing block each raise a
  plain-English RunwayError (the check can actually stop a bad build, not just pass).

The check has no data dependency, so these run without the emit fixture.
"""
from __future__ import annotations

import pytest

import check_caveats_parity
from _util import CAVEATS
from engine import RunwayError

_MARKED = "<!-- CAVEATS:BEGIN -->\n{body}\n<!-- CAVEATS:END -->\n"


def _template_with(caveat_lines):
    """A minimal recommendations.md-shaped string whose CAVEATS block holds the
    given lines. Enough for the extractor; the rest of the template is irrelevant
    to parity."""
    body = "\n".join(f"- {line}" for line in caveat_lines)
    return "# stub template\n\n" + _MARKED.format(body=body)


def _point_at(monkeypatch, tmp_path, text):
    """Redirect the check at a throwaway template file holding `text`."""
    path = tmp_path / "recommendations.md"
    path.write_text(text, encoding="utf-8")
    monkeypatch.setattr(check_caveats_parity, "RECOMMENDATIONS_PATH", path)
    return path


def test_real_repo_files_are_in_parity():
    """The committed prompts/recommendations.md matches engine _util.CAVEATS —
    the positive pin that fails the suite the moment either side drifts."""
    # See test_emit_unit.test_caveats_verbatim_from_engine: the count is pinned so a
    # disclosure can't be added or dropped silently. 5 -> 4 when the design-specific
    # STEM-OPT caveat was removed in the de-binding from design (ratified 2026-07-22).
    assert check_caveats_parity.check_caveats_parity() == len(CAVEATS) == 4


def test_drifted_caveat_raises(monkeypatch, tmp_path):
    """One altered caveat -> RunwayError that names the divergence, not a silent pass."""
    drifted = list(CAVEATS)
    drifted[0] = drifted[0] + " (edited)"
    _point_at(monkeypatch, tmp_path, _template_with(drifted))
    with pytest.raises(RunwayError, match="drifted"):
        check_caveats_parity.check_caveats_parity()


def test_reordered_caveats_raise(monkeypatch, tmp_path):
    """Same strings, wrong order -> still a failure (order is part of parity)."""
    reordered = list(CAVEATS)
    reordered[0], reordered[1] = reordered[1], reordered[0]
    _point_at(monkeypatch, tmp_path, _template_with(reordered))
    with pytest.raises(RunwayError):
        check_caveats_parity.check_caveats_parity()


def test_missing_caveat_raises(monkeypatch, tmp_path):
    """Dropping a caveat is a mismatch (count + content), not a tolerated subset."""
    _point_at(monkeypatch, tmp_path, _template_with(list(CAVEATS)[:-1]))
    with pytest.raises(RunwayError):
        check_caveats_parity.check_caveats_parity()


def test_non_caveat_line_in_block_raises(monkeypatch, tmp_path):
    """A stray non-bullet line inside the markers is rejected before comparison."""
    text = "# stub\n\n<!-- CAVEATS:BEGIN -->\nnot a bullet\n<!-- CAVEATS:END -->\n"
    _point_at(monkeypatch, tmp_path, text)
    with pytest.raises(RunwayError, match="non-caveat line"):
        check_caveats_parity.check_caveats_parity()


def test_missing_block_raises(monkeypatch, tmp_path):
    """No CAVEATS:BEGIN/END markers at all -> the block-missing failure."""
    _point_at(monkeypatch, tmp_path, "# stub template with no markers\n")
    with pytest.raises(RunwayError, match="missing"):
        check_caveats_parity.check_caveats_parity()


def test_absent_file_raises(monkeypatch, tmp_path):
    """The template file itself missing -> a RunwayError, not a bare FileNotFound."""
    monkeypatch.setattr(
        check_caveats_parity, "RECOMMENDATIONS_PATH", tmp_path / "nope.md"
    )
    with pytest.raises(RunwayError, match="missing"):
        check_caveats_parity.check_caveats_parity()
