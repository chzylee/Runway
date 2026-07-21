# Runway

A sponsorship diagnostic for international new-grad designers. It answers two
questions with data instead of folklore:

1. **Who actually sponsors entry-level designers?** — a shortlist of companies
   with *certified, entry-wage (Level I)* design visa filings, built from raw
   US Department of Labor LCA disclosure data.
2. **What should I build to be worth a visa to them?** — a prompt, filled with
   your portfolio, résumé, and the companies you pick from that shortlist, that
   you run in your own LLM to get a plan naming concrete projects to build.

The edge is data-grounding plus judgment, not a directory: every number in the
shortlist traces back to a public DOL filing, and the advice step runs in
**your own** LLM chat — Runway itself never calls a model.

## How it works

- **Layer 1 — deterministic engine (no LLM).** `engine/` filters DOL LCA data
  to certified Level-I design filings and aggregates one row per employer.
  In-pipeline checks (`engine/verify.py`) stop any run that looks wrong.
  `scripts/run.py` runs this and emits the result as static JSON/CSV into
  `web/data/`.
- **Layer 2 — "hiring now?" signal.** Not modeled yet — deferred to a future
  version. An LCA certification is not an open role; treat the shortlist as
  "sponsors, historically," not "hiring today."
- **Layer 3 — the prompt.** The static site in `web/` is the only presentation
  surface. You pick a role, select target companies from the shortlist, add
  your portfolio link (and optionally paste your résumé), and the site fills
  `prompts/recommendations.md` with those inputs and hands you a finished
  prompt to copy. You run it in your own Claude/ChatGPT chat and read the
  result critically — no script in this repo calls an LLM, and nothing you
  enter is sent anywhere by the page itself.

## Run it locally

The site's data (`web/data/<role>.{json,csv}` per registered role, and the
prompt mirror in `web/prompts/`) is committed to the repo, so a fresh clone
already has everything the UI needs — no Python setup, no DOL download,
required just to work on the site.

Requires [Node.js](https://nodejs.org/).

```
npm install
npm run dev
```

This starts a [Vite](https://vite.dev) dev server rooted at `web/` on
`http://localhost:8000` with hot reload — editing `index.html`, `app.js`, or
`styles.css` refreshes the browser automatically, no manual reload.

`npm test` runs the JS test suite (`vitest` + `jsdom`) — a deliberately narrow
set of checks on `web/app.js`: DOM escaping, portfolio URL scheme validation,
and the PromptReady gate's branch logic. It does not cover sort order, CSV
formatting, or rendering details on purpose — see `docs/decision_log.md`
dec. #42 for why.

(The Python engine that produces `web/data/` from raw DOL filings is a
separate, occasional job — see `docs/build_status.md` — not part of the
day-to-day UI workflow.)

## Using the site

1. **Pick a role.** Two are wired: **Design** (web/digital interface, graphic,
   and commercial/industrial design filings) and **UI/UX Design** (a narrower
   role scoped to just web/digital-interface-designer filings — no distinct
   SOC/O*NET code exists for "UI/UX" specifically, so this is the closest
   official match). Picking one fetches its own `data/<role>.json` and shows
   that role's shortlist; the two shortlists are independent, not a filter of
   one another. In the shortlist table, a row whose SOC title is "Web and
   Digital Interface Designers" is annotated "(UI/UX)" for legibility.
2. **Add your inputs.** A portfolio link (required, validated as a URL) and,
   optionally, pasted résumé text. The résumé stays in the browser's memory —
   there is no upload and nothing is sent to a server.
3. **Select target companies** from the shortlist table (checkboxes). The
   caveats above the table and the funnel line are rendered verbatim from
   `<role>.json` — nothing about what a filing means is hardcoded in the UI.
4. **Generate the prompt.** Once ≥1 company is selected and the portfolio URL
   is valid, "Generate prompt" fills `prompts/recommendations.md` with your
   selections and shows it in a copy box. Any input change invalidates an
   already-shown prompt.
5. **Run it yourself.** Copy the prompt into your own Claude/ChatGPT chat and
   review what comes back. There is currently no way to paste that result back
   into the site for a rendered view — that step isn't built yet.

## When something goes wrong

- **"Couldn't load the shortlist"** in the browser — usually means the
  selected role's `web/data/<role>.json` is missing or malformed. On a normal
  clone this shouldn't happen (the files are committed); if you've been
  editing the data pipeline, re-check `scripts/run.py`'s output.
- Anything from the Python engine (`engine/`, `scripts/`) — see
  `docs/build_status.md`; it's a separate, occasional job from the UI
  workflow above.

## Caveats — attached to every applicant-facing output

- An LCA certification is not a hire or an open role.
- OPT is not sponsorship — a new grad's first job is on OPT; sponsorship comes 1-3 years later.
- Design roles are likely not STEM-OPT eligible -> roughly a 12-month OPT window, not 36.
- Employer names are conservatively normalized and may under-merge.
- Career/portfolio guidance, not immigration legal advice.

These live in exactly one place — `engine/_util.py`'s `CAVEATS` — and are
emitted verbatim into every role's `<role>.json` and mirrored into
`prompts/recommendations.md` (`scripts/check_caveats_parity.py` enforces the
two never drift apart).

## Repo map

```
web/                         the static site: index.html + app.js + styles.css
web/app.test.js              narrow vitest suite: escaping, URL validation, PromptReady gate (dec. #42)
web/data/                    committed, site-served shortlist artifacts, per role (design.*, uiux.*)
web/prompts/                 build-written mirror of prompts/recommendations.md (do not hand-edit)
package.json                 dev-only Node tooling (Vite + vitest) for `npm run dev` / `npm test` — web/ only
vitest.config.js             jsdom test environment, scoped to web/**/*.test.js

prompts/recommendations.md   reviewer prompt template (single source; filled client-side, run by you)

engine/sponsors.py           deterministic engine: filter + aggregate (no LLM, no HTML); ROLE_SOC is the role registry
engine/verify.py             in-pipeline checks; a failed check stops the run
scripts/fetch_quarters.py    checks DOL for new quarters + downloads them (HEAD-probe discovery, dec. #43)
scripts/convert_quarters.py  raw DOL xlsx -> narrow parquet (streamed)
scripts/build_shortlist.py   engine -> web/data/<role>.{json,csv} (+ provenance), one role at a time or build_all()
scripts/check_caveats_parity.py  asserts prompts/recommendations.md's caveats match engine/_util.CAVEATS
scripts/run.py               fetch -> convert -> build: regenerates web/data/ (every role) + prompt mirror (occasional, not part of UI dev; --no-fetch to skip the DOL check)
.github/workflows/data-pipeline.yml  weekly + on-demand CI: fetch new quarter -> rebuild -> commit web/data/
data/raw/                    DOL xlsx lands here, auto-downloaded (or drop by hand)  (gitignored)
data/processed/               derived parquet, regenerable      (gitignored)

docs/decision_log.md         every fork in the road, and why
docs/build_status.md         where Runway sits in the Ship Pipeline + what finishes the current build
```

For the current build's position (what's shipped, what's next) see
[`docs/build_status.md`](docs/build_status.md).
