# Runway

A sponsorship diagnostic for international new grads who will need work-visa
sponsorship. It is **title-agnostic by design** — the engine takes SOC codes, not a
role name (dec. #3, and the title-agnostic engine note in the decision log), so any
role can be registered. The roles registered so far are a
scope choice, not the product's audience — see "Using the site" for the current list. It answers two questions with data instead
of folklore:

1. **Who actually sponsors entry-level hires in my role?** — a shortlist of companies
   with *certified, entry-wage (Level I)* visa filings for that role, built from raw
   US Department of Labor LCA disclosure data.
2. **What should I build to be worth a visa to them?** — a prompt, filled with
   your portfolio, résumé, and the companies you pick from that shortlist, that
   you run in your own LLM to get a plan naming concrete projects to build.

The edge is data-grounding plus judgment, not a directory: every number in the
shortlist traces back to a public DOL filing, and the advice step runs in
**your own** LLM chat — Runway itself never calls a model.

## How it works

- **Layer 1 — deterministic engine (no LLM).** `engine/` filters DOL LCA data
  to certified Level-I filings for a registered role and aggregates one row per
  employer.
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

  The prompt asks for a **single JSON object** back, which you paste into the
  site to see rendered. That shape is the contract between the prompt and
  anything that displays the report, and its **single source of truth** is the
  *Output contract* section of [`prompts/recommendations.md`](prompts/recommendations.md)
  — deliberately not restated here, so the two can never drift apart. Read it
  there before building or changing anything that consumes the report.

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

1. **Pick a role.** Five are wired: **Design** (web/digital interface, graphic,
   and commercial/industrial design filings), **UI/UX Design** (a narrower
   role scoped to just web/digital-interface-designer filings — no distinct
   SOC/O*NET code exists for "UI/UX" specifically, so this is the closest
   official match), **Software Engineer**, **Consultant (Management)**, and
   **Consultant (Technology)** — see `docs/decision_log.md` dec. #45/#46 for
   why "Consultant" is two roles, not one. Picking one fetches its own
   `data/<role>.json` and shows that role's shortlist; every role's shortlist
   is independent, not a filter of another's. In the shortlist table, a row
   whose SOC title is "Web and Digital Interface Designers" is annotated
   "(UI/UX)" for legibility.
2. **Add your inputs.** A portfolio link (required, validated as a URL) and,
   optionally, a **file path** to your résumé (dec. #40) plus a note on what
   you're working on. Runway never opens the file; the path travels into the
   prompt so an agent with file access can read it. There is no upload and
   nothing is sent to a server.
3. **Select target companies** from the shortlist table (checkboxes). The
   caveats above the table and the funnel line are rendered verbatim from
   `<role>.json` — nothing about what a filing means is hardcoded in the UI.
4. **Generate the prompt.** Once ≥1 company is selected and the portfolio URL
   is valid, "Generate prompt" fills `prompts/recommendations.md` with your
   selections and shows it in a copy box. Any input change invalidates an
   already-shown prompt.
5. **Run it yourself.** Copy the prompt into your own Claude/ChatGPT chat and
   review what comes back. An agent that can write files will render the report
   and open it for you; otherwise paste the returned JSON into the report page
   (`web/report_template.html`), which has a paste box for exactly that.

## Adding a role

A role is a name plus a list of SOC codes — nothing else. To register one:

1. **Find the SOC codes from real filings, not memory:**
   `python scripts/discover_role.py "<title pattern>" --level I --min-employers 3`
   prints every SOC code certified Level-I filings under that title actually use, ranked by
   distinct employer count. A clean, dominant single code (like `software_engineer`) is a
   one-code role; a title that splits across unrelated occupations (like "Consultant") is
   better registered as two or more narrower roles than one noisy bundle — see
   `docs/decision_log.md` dec. #45/#46 for both shapes worked through.
2. **Add one entry to `engine.sponsors.ROLE_SOC`** — everything downstream
   (`scripts/build_shortlist.py`'s `build_all()`, the verify checks) is already generic per
   role.
3. **Add the role to the frontend:** one `<option>` in `web/index.html`'s role `<select>`, one
   entry in `web/app.js`'s `ROLE_LABELS`.
4. **Write a decision log entry** naming the alternatives and why this SOC list, then run
   `python scripts/run.py --no-fetch` to emit `web/data/<role>.{json,provenance.json,csv}`.

## When something goes wrong

- **"Couldn't load the shortlist"** in the browser — usually means the
  selected role's `web/data/<role>.json` is missing or malformed. On a normal
  clone this shouldn't happen (the files are committed); if you've been
  editing the data pipeline, re-check `scripts/run.py`'s output.
- Anything from the Python engine (`engine/`, `scripts/`) — see
  `docs/build_status.md`; it's a separate, occasional job from the UI
  workflow above.

## Caveats — attached to every applicant-facing output

Every applicant-facing surface carries a short list of caveats about what an LCA
filing does and does not mean. They are **not reproduced here on purpose.** They
live in exactly one place — `engine/_util.py`'s `CAVEATS` — and are emitted
verbatim into every role's `<role>.json`, rendered by the site from that JSON, and
mirrored into `prompts/recommendations.md`, where
`scripts/check_caveats_parity.py` enforces byte-equality as a build gate.

Read them there. A second copy in this file is how a caveat that was deliberately
removed from the engine survived here anyway.

## Repo map

```
web/                         the static site: index.html + app.js + styles.css
web/app.test.js              narrow vitest suite: escaping, URL validation, PromptReady gate (dec. #42)
web/data/                    committed, site-served shortlist artifacts, per role (design.*, uiux.*, software_engineer.*, consultant_management.*, consultant_tech.*)
web/prompts/                 build-written mirror of prompts/recommendations.md (do not hand-edit)
package.json                 dev-only Node tooling (Vite + vitest) for `npm run dev` / `npm test` — web/ only
vitest.config.js             jsdom test environment, scoped to web/**/*.test.js

prompts/recommendations.md   reviewer prompt template (single source; filled client-side, run by you)

engine/sponsors.py           deterministic engine: filter + aggregate (no LLM, no HTML); ROLE_SOC is the role registry
engine/verify.py             in-pipeline checks; a failed check stops the run
scripts/discover_role.py     SOC codes for a title, read from real filings — the first step of "Adding a role" (dec. #45)
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
