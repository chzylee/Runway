"""Render output/private/runway_report.html from the shortlist CSV.

The report is a self-contained one-pager (embedded CSS, no JS, no external
assets) and is private: it may sit next to portfolio and job-search notes.
Two human-owned inputs are merged in when present:

- output/private/hiring_now.csv   - the reviewer fills the "hiring now?"
  column by hand from real postings; the tool only ever creates it blank.
- output/private/gap_read_filled.md - the reviewed gap-read output (see
  prompts/gap_read.md); until it exists the report shows a visible
  "pending review" placeholder and the run still succeeds.
"""
import html
import json
import re

import _util
from _util import CAVEATS, OUTPUT_DIR, OUTPUT_PRIVATE, REPO_ROOT, ensure_dirs, run_cli

import pandas as pd

from engine import RunwayError

CSV_PATH = OUTPUT_DIR / "sponsors_levelI.csv"
PROVENANCE_PATH = OUTPUT_DIR / "sponsors_levelI.provenance.json"
HIRING_NOW_PATH = OUTPUT_PRIVATE / "hiring_now.csv"
GAP_READ_PATH = OUTPUT_PRIVATE / "gap_read_filled.md"
REPORT_PATH = OUTPUT_PRIVATE / "runway_report.html"


def _read_inputs():
    if not CSV_PATH.exists() or not PROVENANCE_PATH.exists():
        raise RunwayError(
            "The shortlist has not been built yet (output/sponsors_levelI.csv is missing).\n"
            "Run the whole pipeline with: python scripts/run.py"
        )
    table = pd.read_csv(CSV_PATH, encoding="utf-8")
    provenance = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    return table, provenance


def _load_or_create_hiring_now(table):
    """Return {employer_key: (hiring_now, notes)}. The tool writes the file
    only when it doesn't exist, and writes it blank - filling it is manual."""
    if not HIRING_NOW_PATH.exists():
        template = table[["employer", "employer_display"]].copy()
        template["hiring_now"] = ""
        template["notes"] = ""
        template.to_csv(HIRING_NOW_PATH, index=False, encoding="utf-8", lineterminator="\n")
        print(
            "[report] created blank output/private/hiring_now.csv - fill the hiring_now "
            "column by hand from real postings (delete the file to regenerate it after "
            "the shortlist changes)"
        )
        return {}
    edited = pd.read_csv(HIRING_NOW_PATH, encoding="utf-8", dtype=str).fillna("")
    missing = [c for c in ("employer", "hiring_now") if c not in edited.columns]
    if missing:
        raise RunwayError(
            f"output/private/hiring_now.csv is missing column(s): {', '.join(missing)}.\n"
            "Keep the columns the template had (employer, employer_display, hiring_now, notes),\n"
            "or delete the file and re-run to get a fresh blank template."
        )
    if "notes" not in edited.columns:
        edited["notes"] = ""
    return {
        row["employer"]: (row["hiring_now"].strip(), row["notes"].strip())
        for _, row in edited.iterrows()
    }


_BOLD = re.compile(r"\*\*(.+?)\*\*")
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")


def _inline_markdown(escaped_line):
    line = _BOLD.sub(r"<strong>\1</strong>", escaped_line)
    return _LINK.sub(r'<a href="\2">\1</a>', line)


def markdown_to_html(text):
    """Just enough markdown for a reviewed gap read: headings, bullet and
    numbered lists, bold, links, paragraphs. Headings are demoted (# -> h3)
    so the injected document nests under the report's own structure."""
    parts, list_tag, paragraph = [], None, []

    def close_list():
        nonlocal list_tag
        if list_tag:
            parts.append(f"</{list_tag}>")
            list_tag = None

    def close_paragraph():
        if paragraph:
            parts.append("<p>" + " ".join(paragraph) + "</p>")
            paragraph.clear()

    for raw_line in text.splitlines():
        line = _inline_markdown(html.escape(raw_line.strip(), quote=False))
        if not line:
            close_paragraph()
            close_list()
            continue
        heading = re.match(r"(#{1,3})\s+(.*)", line)
        bullet = re.match(r"[-*]\s+(.*)", line)
        numbered = re.match(r"\d+[.)]\s+(.*)", line)
        if heading:
            close_paragraph()
            close_list()
            level = len(heading.group(1)) + 2
            parts.append(f"<h{level}>{heading.group(2)}</h{level}>")
        elif bullet or numbered:
            close_paragraph()
            tag = "ul" if bullet else "ol"
            if list_tag != tag:
                close_list()
                parts.append(f"<{tag}>")
                list_tag = tag
            parts.append(f"<li>{(bullet or numbered).group(1)}</li>")
        else:
            close_list()
            paragraph.append(line)
    close_paragraph()
    close_list()
    return "\n".join(parts)


def _gap_read_section():
    if GAP_READ_PATH.exists():
        body = markdown_to_html(GAP_READ_PATH.read_text(encoding="utf-8"))
        return body, False
    placeholder = (
        '<div class="pending"><strong>Gap read pending review.</strong>'
        "<p>To fill this section: run <code>prompts/gap_read.md</code> in your own "
        "Claude/ChatGPT with the applicant's portfolio, the relevant rows from the "
        "shortlist above, and a few real postings gathered by hand. Review the output, "
        "save the approved version to <code>output/private/gap_read_filled.md</code>, "
        "then re-run <code>python scripts/run.py</code>.</p></div>"
    )
    return placeholder, True


def _money(value):
    return "&mdash;" if pd.isna(value) else f"${value:,.0f}"


def _shortlist_rows(table, hiring):
    rows = []
    for _, r in table.iterrows():
        hiring_now, notes = hiring.get(r["employer"], ("", ""))
        hiring_cell = html.escape(hiring_now) if hiring_now else "&mdash;"
        if notes:
            hiring_cell += f'<br><span class="note">{html.escape(notes)}</span>'
        rows.append(
            "<tr>"
            f'<td>{html.escape(str(r["employer_display"]))}</td>'
            f'<td class="num">{int(r["filing_count"])}</td>'
            f'<td>{html.escape(str(r["quarters"]))}</td>'
            f'<td class="center">{"&#10003;" if r["repeat_sponsor"] == "yes" else ""}</td>'
            f'<td>{html.escape(str(r["soc_titles"]))}</td>'
            f'<td>{html.escape(str(r["worksite_states"]))}</td>'
            f'<td class="num">{_money(r["wage_annual_median"])}</td>'
            f"<td>{hiring_cell}</td>"
            "</tr>"
        )
    return "\n".join(rows)


_CSS = """
body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: #1c1c1c;
       max-width: 1000px; margin: 0 auto; padding: 2rem 1.5rem 3rem; line-height: 1.5; }
h1 { margin-bottom: 0.2rem; }
h2 { margin-top: 2.2rem; border-bottom: 1px solid #ddd; padding-bottom: 0.3rem; }
.meta { color: #555; margin-top: 0; }
.caveats { background: #fff7e6; border: 1px solid #e0c377; border-radius: 8px;
           padding: 0.8rem 1.4rem; margin: 1.4rem 0; }
.caveats ul { margin: 0.4rem 0; padding-left: 1.2rem; }
table { border-collapse: collapse; width: 100%; font-size: 0.88rem; }
th, td { border-bottom: 1px solid #ddd; padding: 6px 8px; text-align: left; vertical-align: top; }
th { background: #f4f4f4; }
tr:nth-child(even) td { background: #fafafa; }
.num { text-align: right; white-space: nowrap; }
.center { text-align: center; }
.note { color: #666; font-size: 0.8rem; }
.pending { border: 2px dashed #cc9999; background: #fdf4f4; border-radius: 8px;
           padding: 0.8rem 1.4rem; }
.sourcenote { color: #666; font-size: 0.85rem; }
footer { color: #666; font-size: 0.85rem; margin-top: 2.5rem; border-top: 1px solid #ddd;
         padding-top: 1rem; }
code { background: #f2f2f2; padding: 1px 4px; border-radius: 3px; }
"""


def build_report():
    ensure_dirs()
    table, provenance = _read_inputs()
    hiring = _load_or_create_hiring_now(table)
    gap_html, gap_pending = _gap_read_section()

    quarters = provenance["quarters_used"]
    funnel = provenance["funnel"]
    soc_codes = ", ".join(provenance["filters"]["soc_codes"])
    caveat_items = "\n".join(f"<li>{html.escape(c, quote=False)}</li>" for c in CAVEATS)

    single_quarter_note = (
        "<p class='sourcenote'>Single-quarter run: the repeat-sponsor signal needs at "
        "least two quarters. Convert another quarter to see which employers file "
        "again and again.</p>"
        if len(quarters) == 1 else ""
    )
    wage_excluded = provenance["rows_wage_excluded_from_wage_stats"]
    wage_excluded_note = (
        f"{wage_excluded} filing(s) had a missing wage or a pay unit outside "
        "year/hour/month/week; they are counted in every total but excluded from the "
        "wage statistics. "
        if wage_excluded else ""
    )

    report = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Runway &mdash; Level I design sponsorship diagnostic</title>
<style>{_CSS}</style>
</head>
<body>
<h1>Runway</h1>
<p class="meta">Companies that certify entry-wage (Level&nbsp;I) design visa filings, from US DOL
LCA disclosure data (public record) &mdash; plus the three portfolio projects that would make an
applicant worth a visa to them.</p>
<p class="meta">{len(table)} employers &middot; {funnel["rows_selected"]} certified Level&nbsp;I design filings
&middot; quarters: {html.escape(", ".join(quarters))} &middot; generated {html.escape(provenance["generated_at_utc"])}</p>

<div class="caveats">
<strong>Read this first</strong>
<ul>
{caveat_items}
</ul>
</div>

<h2>Sponsor shortlist</h2>
<p class="sourcenote">Sorted by quarters present, then filing count. The <em>hiring now?</em> column is
filled manually in <code>output/private/hiring_now.csv</code> from real postings &mdash; an LCA
certification says nothing about current openings, and the automated postings check is deferred to v2.</p>
{single_quarter_note}
<table>
<thead>
<tr><th>Employer</th><th>Filings</th><th>Quarters</th><th>Repeat<br>sponsor</th>
<th>SOC titles</th><th>Worksite states</th><th>Median annual<br>wage (from)</th><th>Hiring now?<br>(manual)</th></tr>
</thead>
<tbody>
{_shortlist_rows(table, hiring)}
</tbody>
</table>

<h2>Portfolio gap read &mdash; 3 projects</h2>
{gap_html}

<footer>
<p>Derived from {funnel["rows_total"]:,} LCA rows across {len(quarters)} quarter(s):
{funnel["rows_certified"]:,} certified &rarr; {funnel["rows_soc_matched"]:,} in design SOC codes
({html.escape(soc_codes)}) &rarr; {funnel["rows_selected"]:,} at prevailing-wage Level&nbsp;I.
{wage_excluded_note}Wages are annualized from the filing&#39;s <em>from</em> rate.
Full data (including wage min/max and cities): <code>output/sponsors_levelI.csv</code>.</p>
<p>This document is private: it may contain portfolio and job-search details. The shortlist CSV
alone is public-record data.</p>
</footer>
</body>
</html>
"""
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"[report] wrote {REPORT_PATH.relative_to(REPO_ROOT)}")
    if gap_pending:
        print("[report] gap read: pending review (placeholder rendered - see prompts/gap_read.md)")
    else:
        print("[report] gap read: injected from output/private/gap_read_filled.md")


def main():
    build_report()


if __name__ == "__main__":
    run_cli(main)
