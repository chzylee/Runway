"""Pins for the report handoff: injecting a report JSON into the HTML template.

Why this file exists: the script-block escaping silently failed once during the
build. The escape was written as "\\u003c", lost a backslash in transport, became
"<" -- which IS the character "<" -- so it compiled to replace("<", "<"), a no-op.
The generated page looked fine and executed an injected <script>. Nothing caught it
except a browser test. These pins make that failure loud and cheap instead.
"""

import json

import pytest

from scripts.make_report import TOKEN, build_report_html, escape_for_script_block
from engine import RunwayError

TEMPLATE = f'<html><script type="application/json" id="report-data">{TOKEN}</script></html>'


def test_escape_removes_the_only_sequence_that_can_close_the_tag():
    payload = escape_for_script_block(json.dumps({"a": "</script><script>bad()</script>"}))
    assert "</" not in payload


def test_escaped_payload_still_decodes_to_the_identical_value():
    original = {"a": "</script>", "b": "a < b", "c": "plain"}
    payload = escape_for_script_block(json.dumps(original))
    assert json.loads(payload) == original


def test_non_ascii_survives_untouched():
    """The audience is international students; names are not ASCII."""
    original = {"trait": "José Müller 吉田 — 日本語"}
    payload = escape_for_script_block(json.dumps(original, ensure_ascii=False))
    assert json.loads(payload) == original
    assert "吉田" in payload  # embedded as UTF-8 text, never transformed


def test_injected_page_contains_no_breakout_sequence():
    hostile = {"headline": {"angle": '</script><script>window.pwned=1</script>'}}
    html = build_report_html(hostile, TEMPLATE)
    body = html.split('id="report-data">', 1)[1].split("</script>", 1)[0]
    assert "</" not in body
    assert "window.pwned" in body  # still present, just inert


def test_placeholder_must_appear_exactly_once():
    """A second copy of the token (even in a comment) makes substitution ambiguous."""
    with pytest.raises(RunwayError, match="exactly 1"):
        build_report_html({}, TEMPLATE + TOKEN)
    with pytest.raises(RunwayError, match="exactly 1"):
        build_report_html({}, "<html>no placeholder here</html>")


def test_real_template_has_exactly_one_placeholder():
    from scripts.make_report import TEMPLATE_PATH

    assert TEMPLATE_PATH.exists(), "web/report_template.html is missing"
    assert TEMPLATE_PATH.read_text(encoding="utf-8").count(TOKEN) == 1


def test_fixtures_inject_cleanly(tmp_path):
    """The committed fixtures must round-trip through the real template."""
    from pathlib import Path

    from scripts.make_report import TEMPLATE_PATH

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    fixtures = Path(__file__).parent / "fixtures"
    for name in ("report_valid.json", "report_null_edges.json"):
        data = json.loads((fixtures / name).read_text(encoding="utf-8"))
        html = build_report_html(data, template)
        assert TOKEN not in html
        assert len(html) > len(template)
