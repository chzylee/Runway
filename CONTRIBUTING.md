# Contributing to Runway

Runway is a small project with a narrow job: show which companies actually
sponsor entry-level hires in a role, and hand you a prompt you run yourself.
Contributions that sharpen that are welcome. So are corrections — if the data
looks wrong to you, that is worth an issue.

This file covers the process. The *substance* lives in
[`README.md`](README.md) — how the pipeline works, how to add a role, what
every file is for. It is not repeated here on purpose: two copies of the same
instructions is how one of them goes quietly stale.

## Ways to help

**Report a data problem.** A company that looks wrong, a shortlist that misses
an employer you know sponsors, a SOC code that seems to be catching the wrong
filings. This is the most useful thing you can send, because the whole claim of
the project is that every number traces to a filing.

**Request a role.** Runway is title-agnostic by design — the engine takes SOC
codes, not a role name — so a new role is a small change. Open an issue first;
see below.

**Improve the site or the prompt.** `web/` is a static page and
`prompts/recommendations.md` is the reviewer prompt template. Both take
ordinary pull requests.

**Fix a bug.** Especially anything where the page fails in a way a user cannot
act on.

## Setup

You do **not** need the DOL data to work on this. The site's per-role artifacts
are committed, and the test suite runs entirely on synthetic fixtures, so a
fresh clone can run everything.

For the site (Node):

```
npm install
npm run dev     # Vite dev server on http://localhost:8000
npm test        # vitest — narrow suite over web/app.js
```

For the engine (Python 3.11):

```
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

Run both before opening a pull request. CI runs the same two commands, so a
local failure is a CI failure.

## Adding a role: open an issue first

Do not send a pull request that adds a role. Open a **Role request** issue
instead.

The reason is reproducibility. Every file in `web/data/` is a build output of a
specific pipeline run against a specific set of DOL quarters. If those files
arrive by pull request, there is no way to check them by reading the diff —
they are thousands of rows of aggregated filings, and the guarantee the project
makes to its users is that each one came from a known run. So the maintainer
runs `scripts/run.py` and commits the result.

What the issue needs from you is the part that takes real work: the SOC codes,
found from actual filings rather than from memory.

```
python scripts/discover_role.py "<title pattern>" --level I --min-employers 3
```

Paste that output into the issue. The README's "Adding a role" section explains
how to read it — in particular, when a title that splits across unrelated
occupations should become two narrow roles rather than one noisy bundle.

## What will not be merged

- **Hand-edited files in `web/data/` or `web/prompts/`.** Both are build
  outputs. Change the code that generates them.
- **Caveat text edited anywhere but `scripts/_util.py`'s `CAVEATS`.** Those
  caveats are emitted verbatim into every role's JSON and mirrored into the
  prompt, and `scripts/check_caveats_parity.py` enforces byte-equality as a
  build gate. A second copy is exactly what that gate exists to prevent.
- **A role backed by memory instead of `discover_role.py` output.** Plausible
  SOC codes are the failure mode this project is built to avoid.
- **Anything that makes the page call an LLM or send user input to a server.**
  Runway never calls a model and has no backend. That is a product commitment,
  not an implementation detail — the FAQ makes the promise to users directly.

## Decision log

Non-trivial changes get an entry in [`docs/decision_log.md`](docs/decision_log.md)
naming the alternatives considered and why this one won. Follow the existing
format. A reviewer reading the log a year from now should be able to reconstruct
the choice without you.

## License

By contributing, you agree that your contributions are licensed under the MIT
License, the same terms as the rest of the project. See [`LICENSE`](LICENSE) and
[`NOTICE-DATA.md`](NOTICE-DATA.md).
