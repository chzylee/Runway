## What changed and why

<!-- One paragraph. If it fixes an issue, link it. -->

## Type

- [ ] Site or prompt change (`web/`, `prompts/`)
- [ ] Engine or pipeline change (`engine/`, `scripts/`)
- [ ] Docs
- [ ] Bug fix

<!-- Adding a role? Open a Role request issue instead — see CONTRIBUTING.md. -->

## Checks

- [ ] `npm test` passes
- [ ] `pytest` passes
- [ ] No hand-edited files in `web/data/` or `web/prompts/` (both are build outputs)
- [ ] Caveat text, if touched, was changed only in `scripts/_util.py`'s `CAVEATS`
- [ ] Entry added to `docs/decision_log.md` if this was a non-trivial choice
