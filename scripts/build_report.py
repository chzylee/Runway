"""Runway — build the one-page HTML report (T4 data-grounded part).

Reads output/sponsors_levelI.csv (the engine's artifact) and renders a
self-contained, shareable HTML one-pager: the grounded entry-wage shortlist +
caveats. The gap-read section (her 3 named-company projects) is slotted in from
output/private/gap_read_filled.md if present; otherwise a clearly-marked
placeholder is shown (that section comes from the reviewed LLM step, which needs
her portfolio — see prompts/gap_read.md).

Self-contained HTML (embedded CSS, no JS, no external assets) so it opens
anywhere and is easy to share for early UX feedback. No pandoc dependency.

Output is PRIVATE (output/private/) — it will hold her portfolio-derived
gap-read. Never publish it. The public artifacts are the engine + method +
decision log + the (public-record) shortlist CSV.

Usage:
    python scripts/build_report.py
"""

import argparse
import html
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

CSV_PATH = Path("output/sponsors_levelI.csv")
GAPREAD_PATH = Path("output/private/gap_read_filled.md")
OUT_PATH = Path("output/private/runway_report.html")
UX_SOC = "Web and Digital Interface Designers"  # 15-1255

CSS = """
:root { --ink:#15181d; --muted:#5b6470; --line:#e5e8ec; --accent:#1f6feb; --warn:#9a3412; --warnbg:#fff7ed; }
* { box-sizing:border-box; }
body { font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
       color:var(--ink); max-width:860px; margin:0 auto; padding:48px 24px 96px; }
h1 { font-size:30px; line-height:1.2; margin:0 0 4px; letter-spacing:-0.02em; }
h2 { font-size:20px; margin:40px 0 12px; letter-spacing:-0.01em; }
.sub { color:var(--muted); margin:0 0 8px; }
.lede { font-size:18px; color:var(--ink); background:#f7f9fb; border:1px solid var(--line);
        border-radius:10px; padding:16px 18px; margin:20px 0; }
table { border-collapse:collapse; width:100%; font-size:14px; margin:8px 0 4px; }
th,td { text-align:left; padding:8px 10px; border-bottom:1px solid var(--line); vertical-align:top; }
th { color:var(--muted); font-weight:600; font-size:12px; text-transform:uppercase; letter-spacing:0.04em; }
tr:hover td { background:#fafbfc; }
.badge { display:inline-block; font-size:11px; font-weight:600; padding:1px 7px; border-radius:999px;
         background:#eef4ff; color:var(--accent); }
.badge.ux { background:#e9f9ee; color:#137333; }
.repeat { font-variant-numeric:tabular-nums; font-weight:600; }
.caveats { background:var(--warnbg); border:1px solid #fed7aa; border-radius:10px; padding:8px 18px; }
.caveats li { margin:8px 0; }
.placeholder { border:1px dashed #c3c9d2; border-radius:10px; padding:18px; color:var(--muted); background:#fbfcfd; }
.foot { color:var(--muted); font-size:13px; margin-top:40px; border-top:1px solid var(--line); padding-top:16px; }
code { background:#f0f2f4; padding:1px 5px; border-radius:5px; font-size:13px; }
.stat { display:inline-block; margin-right:28px; }
.stat b { font-size:24px; display:block; line-height:1.1; }
.stat span { color:var(--muted); font-size:13px; }
"""


def fmt_wage(v) -> str:
    if v is None or pd.isna(v):
        return "—"
    return f"${int(v):,}"


def shortlist_rows_html(df: pd.DataFrame, n_quarters: int, limit: int = 40) -> str:
    out = []
    for _, r in df.head(limit).iterrows():
        is_ux = UX_SOC in str(r["soc_titles"])
        emp = html.escape(str(r["employer"]).title())
        ux_badge = '<span class="badge ux">UX/UI</span> ' if is_ux else ""
        qp = int(r["quarters_present"])
        repeat = f'<span class="repeat">{qp}/{n_quarters}</span>' if qp >= 2 else f"{qp}/{n_quarters}"
        wage = fmt_wage(r["wage_annual_median"])
        states = html.escape(str(r["worksite_states"])[:60])
        titles = html.escape(str(r["soc_titles"]))
        out.append(
            f"<tr><td>{ux_badge}{emp}</td><td>{int(r['filing_count'])}</td>"
            f"<td>{repeat}</td><td>{titles}</td><td>{states}</td><td>{wage}</td></tr>"
        )
    return "\n".join(out)


def md_to_basic_html(md: str) -> str:
    """Minimal markdown -> HTML (headings, bullets, bold) for the gap-read block."""
    lines, out, in_ul = md.splitlines(), [], False
    for ln in lines:
        s = ln.rstrip()
        if s.startswith("### "):
            if in_ul: out.append("</ul>"); in_ul = False
            out.append(f"<h3>{html.escape(s[4:])}</h3>")
        elif s.startswith("## "):
            if in_ul: out.append("</ul>"); in_ul = False
            out.append(f"<h2>{html.escape(s[3:])}</h2>")
        elif s.startswith(("- ", "* ")):
            if not in_ul: out.append("<ul>"); in_ul = True
            out.append(f"<li>{html.escape(s[2:])}</li>")
        elif not s:
            if in_ul: out.append("</ul>"); in_ul = False
        else:
            if in_ul: out.append("</ul>"); in_ul = False
            out.append(f"<p>{html.escape(s)}</p>")
    if in_ul: out.append("</ul>")
    html_out = "\n".join(out)
    # bold
    import re
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html_out)


def gapread_html() -> str:
    if GAPREAD_PATH.exists():
        return md_to_basic_html(GAPREAD_PATH.read_text(encoding="utf-8"))
    return (
        '<div class="placeholder">'
        "<strong>Gap-read pending.</strong> The 3 named-company portfolio projects "
        "come from the reviewed LLM step, which needs her portfolio + a handful of "
        "live postings from the shortlist below. Run <code>prompts/gap_read.md</code> "
        "in your own Claude/ChatGPT, review the output, save it to "
        "<code>output/private/gap_read_filled.md</code>, and rebuild this report."
        "</div>"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(CSV_PATH))
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    n_emp = len(df)
    n_repeat = int((df["quarters_present"] >= 2).sum())
    n_filings = int(df["filing_count"].sum())
    n_ux = int(df["soc_titles"].str.contains(UX_SOC, na=False).sum())
    quarters = sorted(q for q in set(", ".join(df["quarters"].astype(str)).replace(" ", "").split(",")) if q)
    n_quarters = len(quarters)
    # Human phrase for the data window, honest about how much data this actually is.
    if n_quarters <= 1:
        window = f"in {quarters[0]}" if quarters else "in the DOL filing data"
        window_title = "One quarter"
    elif n_quarters >= 4:
        window = f"across {n_quarters} quarters ({quarters[0]}–{quarters[-1]})"
        window_title = f"{n_quarters} quarters"
    else:
        window = f"across {n_quarters} quarters ({quarters[0]}–{quarters[-1]})"
        window_title = f"{n_quarters} quarters only"

    body = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Runway — entry-wage design sponsor shortlist</title>
<style>{CSS}</style></head><body>

<h1>Runway</h1>
<p class="sub">Grounded shortlist of companies that sponsor <strong>entry-wage</strong> designers, plus your portfolio gap-read.</p>

<div class="lede">
These are companies that <strong>actually certified an entry-wage (Level&nbsp;I) design visa filing</strong>
{window} — read straight off mandated DOL filings, not a directory of "who sponsors anyone."
The list answers <em>who sponsors at the new-grad wage tier</em>. It does not promise they're hiring you this month
(see caveats).
</div>

<p>
<span class="stat"><b>{n_emp}</b><span>companies</span></span>
<span class="stat"><b>{n_repeat}</b><span>repeat sponsors (≥2 quarters)</span></span>
<span class="stat"><b>{n_ux}</b><span>hire Web/Digital Interface (UX/UI)</span></span>
<span class="stat"><b>{n_filings}</b><span>certified filings</span></span>
</p>

<h2>Your gap-read &amp; 3 named-company projects</h2>
{gapread_html()}

<h2>The grounded shortlist</h2>
<p class="sub">Sorted by repeat-sponsorship (the strongest signal), then filing count.
<span class="badge ux">UX/UI</span> marks companies that filed under the Web &amp; Digital Interface Designers code (15-1255).</p>
<table>
<thead><tr><th>Company</th><th>Filings</th><th>Quarters</th><th>Design role(s) filed</th><th>Worksite state(s)</th><th>Median wage*</th></tr></thead>
<tbody>
{shortlist_rows_html(df, n_quarters)}
</tbody>
</table>
<p class="sub">* Annualized from the certified filing's <code>WAGE_RATE_OF_PAY_FROM</code>; salary is a secondary signal here. Full list in <code>output/sponsors_levelI.csv</code>.</p>

<h2>Read this before you act — caveats</h2>
<ul class="caveats">
<li><strong>An LCA is not a hire-now signal.</strong> A certified filing means the employer filed to be <em>able</em> to sponsor. New grads typically start on OPT/STEM-OPT. This list = "who sponsors at entry wage," not "who will hire you this month." Eyeball each company's live postings before counting on it.</li>
<li><strong>Design is likely not STEM-OPT eligible</strong> → roughly a <strong>12-month</strong> OPT runway, not 36. Plan your timeline around the shorter window.</li>
<li><strong>{window_title}, design SOCs only.</strong> A company's absence here does not mean it never sponsors — only that it didn't certify an entry-wage design filing in this window. {"A single quarter is a thin sample — download a full fiscal year for a stronger repeat-sponsor signal." if n_quarters <= 1 else ""}</li>
<li><strong>This is career/portfolio guidance, not immigration legal advice.</strong></li>
</ul>

<p class="foot">
Source: U.S. DOL OFLC LCA Programs disclosure data, {", ".join(quarters)} ·
filter: <code>CASE_STATUS = Certified</code>, SOC ∈ {{15-1255, 27-1024, 27-1021}}, <code>PW_WAGE_LEVEL = I</code> ·
employer counts grouped by normalized name. Engine: <code>engine/sponsors.py</code> · verification passes (<code>engine/verify.py</code>).<br>
Where this data comes from (and how to pull it yourself): the free, mandated DOL disclosure files at
<a href="https://www.dol.gov/agencies/eta/foreign-labor/performance">dol.gov/agencies/eta/foreign-labor/performance</a>
→ Disclosure Data → LCA Programs (H-1B, H-1B1, E-3).<br>
<strong>Private.</strong> This report is for her only — do not publish.
</p>
</body></html>"""

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(body, encoding="utf-8")
    print(f"wrote {OUT_PATH}  ({n_emp} companies, {n_repeat} repeat sponsors)")


if __name__ == "__main__":
    main()
