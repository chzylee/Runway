"""Inject a report JSON into web/report_template.html and write a standalone page.

This is the handoff step, in one tested place. An agent that ran the
recommendations prompt (or a person with a saved JSON reply) runs:

    python scripts/make_report.py report.json -o report.html

...and opens the result. No server, no upload, no paste.

WHY THIS IS A SCRIPT AND NOT AN INSTRUCTION
The substitution needs exactly one escaping rule, and that rule is easy to get
subtly, silently wrong. While building this, an escape written as "\\u003c" lost a
backslash in transport and became "<" -- which *is* the character "<" -- so the
replacement compiled to replace("<", "<"), a no-op that still looked correct and
let a </script> payload execute. The failure was invisible without a test. Keeping
the rule here (with a raw string, and pinned by tests/test_make_report.py) means
nobody re-derives it under pressure.

THE RULE
Inside <script type="application/json">, the ONLY sequence that can break out is
"</". Replacing it with "<\\/" is enough: in a JSON string, \\/ is a valid escape for
/, so the payload still parses to the identical value while the HTML parser never
sees a closing tag. Nothing else needs escaping, and the JSON stays human-readable.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _util import force_utf8, run_cli

from engine import RunwayError

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = REPO_ROOT / "web" / "report_template.html"
TOKEN = "__REPORT_JSON__"


def escape_for_script_block(json_text: str) -> str:
    """Make a JSON string safe to embed in an HTML <script> block.

    Only "</" can terminate the block early. r"<\\/" keeps the HTML parser out of
    it while remaining valid JSON that decodes to the same value.
    """
    return json_text.replace("</", r"<\/")


def build_report_html(data, template_text: str) -> str:
    occurrences = template_text.count(TOKEN)
    if occurrences != 1:
        # A second copy of the token (even in a comment) makes "replace the token"
        # ambiguous and can corrupt the wrong line.
        raise RunwayError(
            f"{TEMPLATE_PATH.name}: expected exactly 1 '{TOKEN}' placeholder, "
            f"found {occurrences}. The token must appear once, in the report-data block."
        )
    payload = escape_for_script_block(json.dumps(data, ensure_ascii=False))
    if "</" in payload:
        raise RunwayError("escaping failed: '</' still present after escaping")
    return template_text.replace(TOKEN, payload)


def main(argv=None) -> int:
    force_utf8()
    ap = argparse.ArgumentParser(description="Render a Runway report JSON into a standalone HTML page.")
    ap.add_argument("report_json", help="path to the JSON the LLM returned")
    ap.add_argument("-o", "--out", default="report.html", help="output HTML path (default: report.html)")
    args = ap.parse_args(argv)

    src = Path(args.report_json)
    if not src.exists():
        raise RunwayError(f"no such file: {src}. Save the LLM's JSON reply first, then pass its path.")
    raw = src.read_text(encoding="utf-8")

    # Tolerate a ```json fence and prose around the object -- a real run appended a
    # plain-English note after the closing brace.
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise RunwayError(f"{src}: no JSON object found in that file.")
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError as exc:
        raise RunwayError(f"{src}: that isn't valid JSON ({exc.msg} at line {exc.lineno}).") from exc

    if not TEMPLATE_PATH.exists():
        raise RunwayError(f"missing template: {TEMPLATE_PATH}")
    html = build_report_html(data, TEMPLATE_PATH.read_text(encoding="utf-8"))

    out = Path(args.out)
    out.write_text(html, encoding="utf-8")
    print(f"[report] wrote {out}  ({out.stat().st_size:,} bytes)")
    print(f"[report] open it: {out.resolve().as_uri()}")
    return 0


if __name__ == "__main__":
    run_cli(main)
