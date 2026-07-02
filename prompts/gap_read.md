# Gap-read prompt (Layer 3 — reviewed-advisor judgment)

**How to use.** This is the LLM step. Run it in your own Claude/ChatGPT
subscription (not in the engine). You are the reviewer — the model drafts, you
approve/edit before anything reaches the applicant. Fill the four bracketed
blocks, paste, then sanity-check the output against the caveats at the bottom.

Inputs you provide:
- `[[PORTFOLIO]]` — the applicant's portfolio as text + links (case studies,
  roles, tools, years).
- `[[SHORTLIST]]` — paste the relevant rows of `output/sponsors_levelI.csv`
  (employer, soc_titles, worksite_states, quarters_present). Prefer
  repeat-sponsors (quarters_present ≥ 2) and companies whose role matches the
  applicant's (Web & Digital Interface Designers / 15-1255 for UI/UX).
- `[[LIVE_POSTINGS]]` — for ~5–8 shortlist companies, paste the text of one real
  current entry-level design posting each (you gather these by hand). This is
  what makes the advice named-company specific rather than generic.
- `[[TARGET_ROLE]]` — e.g. "new-grad UI/UX / product designer".

---

## PROMPT

You are an exacting design-portfolio advisor helping an international new-grad
designer who needs US visa sponsorship. Be concrete and honest; do not flatter.
The applicant's livelihood depends on this, so never overstate their odds.

Here is the applicant's portfolio:
[[PORTFOLIO]]

Here is a data-grounded shortlist of companies that have *certified entry-wage
(Level I) design LCAs* in the DOL window the shortlist covers (they demonstrably
sponsor at the new-grad wage tier). Repeat-sponsors (quarters_present ≥ 2) are
the strongest signals:
[[SHORTLIST]]

Here are real current entry-level design postings at some of those companies:
[[LIVE_POSTINGS]]

The applicant's target role: [[TARGET_ROLE]]

Do the following, grounded in the specific companies and postings above — not
generic portfolio advice:

1. **Gap-read.** For the applicant's portfolio vs. these specific companies'
   entry postings, name the 3–5 most important gaps between what the portfolio
   shows and what these employers' postings actually ask for. Tie each gap to a
   named company/posting.

2. **3 named-company projects.** Propose exactly 3 portfolio projects that would
   make the applicant worth a visa to *named* companies on this list. Each project:
   - Names the 1–2 specific shortlist companies it targets and why (cite the
     posting requirement it answers).
   - States the gap it closes (from step 1).
   - Is scoped to be finishable by one designer in 2–4 weeks.
   - Specifies the artifact (screens, case study, prototype) and the single
     thing a reviewer at that company would look for.

3. **What to cut/keep.** One line on which existing portfolio pieces to lead with
   for these companies, and which to drop.

Output as: GAPS (bulleted), then PROJECT 1/2/3 (named-company, gap, scope,
artifact), then LEAD-WITH/CUT. Keep it tight. Flag anything you're unsure about
rather than inventing.

---

## OPT-now eyeball (manual, replaces the cut Layer A)

For each shortlist company you'd actually point the applicant at, manually
check: **do they have a live entry-level design role right now?** (careers page
/ LinkedIn). LCA data proves "will sponsor eventually," not "hiring now."
Record each answer — yes / no / unclear — in `output/private/hiring_now.csv`
(created blank the first time the report builds), then rerun
`python scripts/run.py` so the report's "Hiring now?" column shows it. This one
check is the v1 stand-in for the automated OPT-now pipeline (cut to v2).

## Caveats to preserve in any output to the applicant (do not soften)

- **An LCA certification is not a hire or an open role.** A certified LCA means
  the employer filed to be *able* to sponsor. The list answers "who sponsors at
  entry wage," not "who will hire you this month."
- **OPT is not sponsorship.** A new grad's first job is on OPT; sponsorship
  typically comes 1–3 years later.
- **Design is likely NOT STEM-OPT eligible** → ~12-month OPT runway, not 36.
  This shortens the timeline; say so plainly.
- **Employer names are conservatively normalized and may under-merge** — the
  same parent company can appear under more than one legal spelling.
- **Whatever window the shortlist covers, design SOCs only.** Absence from the
  list ≠ "never sponsors."
- This is **career/portfolio guidance, not immigration legal advice.**
