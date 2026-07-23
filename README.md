# Runway

**Live site: <https://chzylee.github.io/Runway/>**

A sponsorship diagnostic for international new grads who will need work-visa
sponsorship. It is **title-agnostic by design**: the engine takes SOC codes, not
a role name (dec. #3, and the title-agnostic engine note in the decision log),
so any role can be registered. The roles registered so far are a scope choice,
not the product's audience. See "Using the site" for the current list.

Runway answers two questions with data instead of folklore:

1. **Who actually sponsors entry-level hires in my role?** A shortlist of
   companies with *certified, entry-wage (Level I)* visa filings for that role,
   built from raw US Department of Labor LCA disclosure data.
2. **What should I build to be worth a visa to them?** A prompt, filled with
   your portfolio, résumé, and the companies you pick from that shortlist, that
   you run in your own LLM to get a plan naming concrete projects to build.

Every number in the shortlist traces back to a public DOL filing, and the
advice step runs in **your own** LLM chat. Runway never calls a model.

## Customizing Runway

Runway is simple on purpose so people can take it, improve it, and share what they make.
This is a guide to customizing Runway. Post what you make on LinkedIn and
[share it with me](https://www.linkedin.com/in/noah-lee-dev/). I'll share what people build.

### The design surface

| File | What it does |
| --- | --- |
| `web/index.html` | the main page: role picker, inputs, shortlist table, prompt box |
| `web/styles.css` | every style on the site |
| `web/faq.html` | the "How this works" page |
| `web/report_template.html` | renders the report your LLM returns |

Every color lives in nine custom properties at the top of `web/styles.css`.
Change those and the whole site changes. Past that, nothing is precious: type,
spacing, layout, structure, copy, all of it is yours to redo.

For a live-reloading local server, `npm install` then `npm run dev` (details
under "[Run it locally](#run-it-locally)"). You can also edit `web/styles.css` straight on
github.com and skip cloning entirely.

### Publish your version

Your fork deploys exactly the way this one does, and there is nothing to build.

1. Fork the repo on GitHub.
2. Open the **Actions** tab in your fork and enable workflows.
3. Go to **Settings → Pages** and set **Source** to **GitHub Actions**.
4. Edit something under `web/` and commit it to `main`.
5. About a minute later your version is live at
   `https://<your-username>.github.io/Runway/`.

Every later push to `main` that touches `web/` redeploys on its own.

### Three things worth knowing before you rearrange

**`app.js` finds controls by their element IDs.** Rename an `id` in
`index.html` and that control goes quiet. Move it, restyle it, or wrap it in
anything you like; just carry the `id` along.

**The report has a shape.** `prompts/recommendations.md` asks the LLM for a
specific JSON object, and `report_template.html` renders that object. Both
sides are yours. Change them together and everything holds.

**You do not need Python or the DOL download.** `web/data/*.json` is committed
and ready to serve. If you want a fork that stays current without ever running
the pipeline, point your fetch at `https://chzylee.github.io/Runway/data/`,
which serves `Access-Control-Allow-Origin: *`.

#### Recommendation: Leave caveats section on the page.

Keep the caveats callout and the provenance line. They are what let a reader
trust the numbers, and that trust is the actual product here. The MIT license
lets you strip them, so this is a request rather than a rule.

When you ship yours, post it and [tag me]((https://www.linkedin.com/in/noah-lee-dev/)).
It makes a real portfolio piece: a live site, real public data, real people using it.

## How it works

- **Layer 1: the deterministic engine (no LLM).** `engine/` filters DOL LCA
  data to certified Level-I filings for a registered role and aggregates one
  row per employer. In-pipeline checks (`engine/verify.py`) stop any run that
  looks wrong. `scripts/run.py` runs this and writes the result as static
  JSON/CSV into `web/data/`.
- **Layer 2: the "hiring now?" signal.** Not modeled yet, deferred to a future
  version. An LCA certification is not an open role, so treat the shortlist as
  "sponsors, historically," not "hiring today."
- **Layer 3: the prompt.** The static site in `web/` is the only presentation
  surface. You pick a role, select target companies from the shortlist, add
  your portfolio link (and optionally paste your résumé), and the site fills
  `prompts/recommendations.md` with those inputs and hands you a finished
  prompt to copy. You run it in your own Claude/ChatGPT chat and read the
  result critically. No script in this repo calls an LLM, and the page itself
  sends nothing you enter anywhere.

  The prompt asks for a **single JSON object** back, which you paste into the
  site to see rendered. That shape is the contract between the prompt and
  anything that displays the report, and its **single source of truth** is the
  *Output contract* section of [`prompts/recommendations.md`](prompts/recommendations.md).
  It is deliberately not restated here, so the two can never drift apart. Read
  it there before building or changing anything that consumes the report.

## Run it locally

The site's data (`web/data/<role>.{json,csv}` per registered role, plus the
prompt mirror in `web/prompts/`) is committed, so a fresh clone already has
everything the UI needs. Working on the site takes no Python setup and no DOL
download.

Requires [Node.js](https://nodejs.org/).

```
npm install
npm run dev
```

This starts a [Vite](https://vite.dev) dev server rooted at `web/` on
`http://localhost:8000` with hot reload, so editing `index.html`, `app.js`, or
`styles.css` refreshes the browser for you.

`npm test` runs the JS test suite (`vitest` + `jsdom`), a deliberately narrow
set of checks on `web/app.js`: DOM escaping, portfolio URL scheme validation,
and the PromptReady gate's branch logic. It leaves out sort order, CSV
formatting, and rendering details on purpose. See `docs/decision_log.md`
dec. #42 for why.

The Python engine that produces `web/data/` from raw DOL filings is a separate,
occasional job (see `docs/build_status.md`), not part of the day-to-day UI
workflow.

## Using the site

1. **Pick a role.** Five are wired: **Design** (web/digital interface, graphic,
   and commercial/industrial design filings), **UI/UX Design** (a narrower role
   scoped to web/digital-interface-designer filings only, since no distinct
   SOC/O\*NET code exists for "UI/UX" and this is the closest official match),
   **Software Engineer**, **Consultant (Management)**, and **Consultant
   (Technology)**. See `docs/decision_log.md` dec. #45/#46 for why "Consultant"
   is two roles rather than one. Picking a role fetches its own
   `data/<role>.json` and shows that role's shortlist; every shortlist is
   independent, not a filter of another. In the table, a row whose SOC title is
   "Web and Digital Interface Designers" is annotated "(UI/UX)" for legibility.
2. **Add your inputs.** A portfolio link (required, validated as a URL) and,
   optionally, a **file path** to your résumé (dec. #40) plus a note on what
   you're working on. Runway never opens the file; the path travels into the
   prompt so an agent with file access can read it. There is no upload and
   nothing goes to a server.
3. **Select target companies** from the shortlist table (checkboxes). The
   caveats above the table and the funnel line render verbatim from
   `<role>.json`, so the UI hardcodes nothing about what a filing means.
4. **Generate the prompt.** Once you have picked at least one company and the
   portfolio URL is valid, "Generate prompt" fills `prompts/recommendations.md`
   with your selections and shows it in a copy box. Changing any input
   invalidates a prompt already on screen.
5. **Run it yourself.** Copy the prompt into your own Claude/ChatGPT chat and
   review what comes back. An agent that can write files will render the report
   and open it for you; otherwise paste the returned JSON into the report page
   (`web/report_template.html`), which has a paste box for exactly that.

## Adding a role

A role is a name plus a list of SOC codes, and nothing else. To register one:

1. **Find the SOC codes from real filings, not memory:**
   `python scripts/discover_role.py "<title pattern>" --level I --min-employers 3`
   prints every SOC code that certified Level-I filings under that title
   actually use, ranked by distinct employer count. A clean, dominant single
   code (like `software_engineer`) makes a one-code role. A title that splits
   across unrelated occupations (like "Consultant") works better as two or more
   narrow roles than as one noisy bundle. See `docs/decision_log.md` dec.
   #45/#46 for both shapes worked through.
2. **Add one entry to `engine.sponsors.ROLE_SOC`.** Everything downstream
   (`scripts/build_shortlist.py`'s `build_all()`, the verify checks) is already
   generic per role.
3. **Add the role to the frontend:** one `<option>` in `web/index.html`'s role
   `<select>`, one entry in `web/app.js`'s `ROLE_LABELS`.
4. **Write a decision log entry** naming the alternatives and why this SOC
   list, then run `python scripts/run.py --no-fetch` to emit
   `web/data/<role>.{json,provenance.json,csv}`.

## When something goes wrong

- **"Couldn't load the shortlist"** in the browser usually means the selected
  role's `web/data/<role>.json` is missing or malformed. On a normal clone this
  shouldn't happen, since the files are committed. If you have been editing the
  data pipeline, re-check `scripts/run.py`'s output.
- Anything from the Python engine (`engine/`, `scripts/`) belongs to
  `docs/build_status.md`, a separate and occasional job from the UI workflow
  above.

## Caveats, attached to every applicant-facing output

Every applicant-facing surface carries a short list of caveats about what an LCA
filing does and does not mean. They are **not reproduced here on purpose.** They
live in exactly one place, `scripts/_util.py`'s `CAVEATS`, and go verbatim into
every role's `<role>.json`, get rendered by the site from that JSON, and are
mirrored into `prompts/recommendations.md`, where
`scripts/check_caveats_parity.py` enforces byte-equality as a build gate.

Read them there. A second copy in this file is how a caveat that was
deliberately removed from the engine survives anyway.

## Repo map

```
web/                         the static site: index.html + app.js + styles.css
web/app.test.js              narrow vitest suite: escaping, URL validation, PromptReady gate (dec. #42)
web/data/                    committed, site-served shortlist artifacts, per role (design.*, uiux.*, software_engineer.*, consultant_management.*, consultant_tech.*)
web/prompts/                 build-written mirror of prompts/recommendations.md (do not hand-edit)
package.json                 dev-only Node tooling (Vite + vitest) for `npm run dev` / `npm test`, web/ only
vitest.config.js             jsdom test environment, scoped to web/**/*.test.js

prompts/recommendations.md   reviewer prompt template (single source; filled client-side, run by you)

engine/sponsors.py           deterministic engine: filter + aggregate (no LLM, no HTML); ROLE_SOC is the role registry
engine/verify.py             in-pipeline checks; a failed check stops the run
scripts/discover_role.py     SOC codes for a title, read from real filings; the first step of "Adding a role" (dec. #45)
scripts/fetch_quarters.py    checks DOL for new quarters + downloads them (HEAD-probe discovery, dec. #43)
scripts/convert_quarters.py  raw DOL xlsx -> narrow parquet (streamed)
scripts/build_shortlist.py   engine -> web/data/<role>.{json,csv} (+ provenance), one role at a time or build_all()
scripts/check_caveats_parity.py  asserts prompts/recommendations.md's caveats match scripts/_util.CAVEATS
scripts/run.py               fetch -> convert -> build: regenerates web/data/ (every role) + prompt mirror (occasional, not part of UI dev; --no-fetch to skip the DOL check)
.github/workflows/data-pipeline.yml  weekly + on-demand CI: fetch new quarter -> rebuild -> commit web/data/
.github/workflows/pages.yml  deploys web/ to GitHub Pages on any push to main that touches it
data/raw/                    DOL xlsx lands here, auto-downloaded (or drop by hand)  (gitignored)
data/processed/               derived parquet, regenerable      (gitignored)

docs/decision_log.md         every fork in the road, and why
docs/build_status.md         where Runway sits in the Ship Pipeline + what finishes the current build

CONTRIBUTING.md              how to help, what will not be merged, why roles go through issues
LICENSE                      MIT
NOTICE-DATA.md               licensing of the DOL data and the derived artifacts in web/data/
.github/ISSUE_TEMPLATE/      issue forms: role request, data problem, bug, idea
.github/workflows/ci.yml     pytest + vitest on every pull request
```

For the current build's position (what's shipped, what's next) see
[`docs/build_status.md`](docs/build_status.md).

## Contributing

Contributions are welcome, especially corrections. If a company or a number in
the shortlist looks wrong to you, that is worth an issue. See
[`CONTRIBUTING.md`](CONTRIBUTING.md) for setup and what will not be merged.

One rule worth stating here: **a new role goes through an issue, not a pull
request.** Everything in `web/data/` is a build output of a specific pipeline
run, so the maintainer generates it. Bring the SOC codes from
`scripts/discover_role.py` and the rest is quick.

The test suites (`npm test`, `pytest`) run on every pull request and need no DOL
data. Both are hermetic.

## License

MIT, see [`LICENSE`](LICENSE).

The underlying DOL LCA data is a work of the US federal government and is not
subject to domestic copyright. The derived artifacts in `web/data/` are MIT like
the code that generates them, and [`NOTICE-DATA.md`](NOTICE-DATA.md) spells this
out.

Runway is career and portfolio guidance, not immigration legal advice.
