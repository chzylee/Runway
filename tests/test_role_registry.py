"""Pins that a registered role is registered *everywhere*, and that every role ships.

WHY THIS FILE EXISTS
Adding a role touches five places that have no link between them: engine.ROLE_SOC,
a select option in index.html, a label in app.js, the emitted data bundle, and the
curated standout-paths file. Miss one and the failure is quiet and role-specific -
a dropdown entry that loads nothing, or a role whose report silently omits a
section - so it survives any test that only exercises the default role.

The size pin is here for a related reason. Two roles once generated prompts of
172 KB and 207 KB because a pattern list scaled with the number of employers.
That is not merely awkward to paste: the output contract sits at the END of the
prompt, so a truncated paste costs the model the schema and presents as "it
ignored the format" rather than as a length problem.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from engine.sponsors import ROLE_SOC

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB = REPO_ROOT / "web"
DATA = WEB / "data"

ROLES = sorted(ROLE_SOC)

# Ceiling for the JSON handed to the prompt via {{ROLE_PATTERNS}}. Comfortably
# above every current role and far below the point where a paste gets truncated.
MAX_PATTERNS_CHARS = 30_000


def _read(p: Path) -> str:
    assert p.exists(), f"missing: {p.relative_to(REPO_ROOT)}"
    return p.read_text(encoding="utf-8")


def test_at_least_one_role_is_registered() -> None:
    assert ROLES, "engine.ROLE_SOC is empty - the site has nothing to offer"


@pytest.mark.parametrize("role", ROLES)
def test_role_is_selectable_in_the_page(role: str) -> None:
    html = _read(WEB / "index.html")
    assert f'<option value="{role}"' in html, (
        f"'{role}' is in ROLE_SOC but has no <option> - nobody can pick it"
    )


@pytest.mark.parametrize("role", ROLES)
def test_role_has_a_display_label(role: str) -> None:
    app = _read(WEB / "app.js")
    block = re.search(r"const ROLE_LABELS = \{(.*?)\};", app, re.S)
    assert block, "could not find ROLE_LABELS in app.js"
    assert re.search(rf"\b{re.escape(role)}\s*:", block.group(1)), (
        f"'{role}' has no entry in ROLE_LABELS - it would render as its raw key"
    )


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("suffix", [".json", ".provenance.json", ".csv"])
def test_role_ships_its_data(role: str, suffix: str) -> None:
    assert (DATA / f"{role}{suffix}").exists(), (
        f"web/data/{role}{suffix} is missing - run: python scripts/run.py --no-fetch"
    )


@pytest.mark.parametrize("role", ROLES)
def test_role_bundle_is_usable(role: str) -> None:
    """The two fields app.js refuses to load without, plus a non-empty shortlist."""
    d = json.loads(_read(DATA / f"{role}.json"))
    assert isinstance(d.get("employers"), list) and d["employers"], (
        f"{role}.json has no employers - the shortlist would render empty"
    )
    assert isinstance(d.get("caveats"), list) and d["caveats"], (
        f"{role}.json has no caveats - the site renders them from this file, never hardcoded"
    )


@pytest.mark.parametrize("role", ROLES)
def test_no_orphan_option_in_the_page(role: str) -> None:
    """Reverse direction: every dropdown entry must be a real registered role."""
    html = _read(WEB / "index.html")
    offered = {v for v in re.findall(r'<option value="([a-z_]+)"', html) if v}
    unknown = offered - set(ROLE_SOC)
    assert not unknown, (
        f"index.html offers roles that are not in ROLE_SOC: {sorted(unknown)} - "
        f"picking one fetches a data file that does not exist"
    )


@pytest.mark.parametrize("role", ROLES)
def test_standout_paths_are_curated_and_well_formed(role: str) -> None:
    """A role may legitimately ship without curated paths, but a malformed file may not.

    Absent is a supported state: the prompt omits the section. A file that exists
    but is broken is not - it would reach the model as garbage it was told to
    select from.
    """
    f = DATA / f"{role}.standout_paths.json"
    if not f.exists():
        pytest.skip(f"{role} has no curated standout paths yet (supported: section is omitted)")
    d = json.loads(_read(f))
    assert d.get("role") == role, f"{f.name} declares role '{d.get('role')}'"
    assert d.get("kind") == "curated-editorial", (
        f"{f.name} must declare kind=curated-editorial - it is not DOL-derived and "
        f"must not be mistaken for data that traces to a filing"
    )
    paths = d.get("paths")
    assert isinstance(paths, list) and paths, f"{f.name} has no paths"
    seen_ranks = set()
    for p in paths:
        for field in ("rank", "path", "what_it_is", "why_it_signals", "source"):
            assert p.get(field), f"{f.name}: a path is missing '{field}'"
        assert p["rank"] not in seen_ranks, f"{f.name}: duplicate rank {p['rank']}"
        seen_ranks.add(p["rank"])
        # The evidence bar: every path carries a checkable source, never a bare claim.
        assert str(p["source"]).startswith("http"), (
            f"{f.name}: path '{p['path']}' has no linkable source"
        )
    assert seen_ranks == set(range(1, len(paths) + 1)), (
        f"{f.name}: ranks must be 1..n with no gaps, got {sorted(seen_ranks)}"
    )


@pytest.mark.parametrize("role", ROLES)
def test_prompt_payload_stays_pasteable(role: str) -> None:
    """Guards the truncation failure, applying the same caps app.js applies.

    Kept in sync with PROMPT_TITLE_CAP / PROMPT_TOKEN_CAP / PROMPT_NAICS_CAP in
    web/app.js. If those change, this number should be re-checked rather than
    merely raised.
    """
    patterns = json.loads(_read(DATA / f"{role}.json")).get("patterns")
    if not patterns:
        pytest.skip(f"{role} emits no patterns")
    jt = dict(patterns.get("job_titles") or {})
    top = lambda xs, n: sorted(xs or [], key=lambda x: -x.get("employers", 0))[:n]
    jt["distinct_titles"] = top(jt.get("distinct_titles"), 40)
    jt["recurring_tokens"] = top(jt.get("recurring_tokens"), 25)
    trimmed = {**patterns, "job_titles": jt,
               "industry_naics2": top(patterns.get("industry_naics2"), 10)}
    size = len(json.dumps(trimmed, indent=2))
    assert size <= MAX_PATTERNS_CHARS, (
        f"{role} would inject {size:,} chars of patterns (cap {MAX_PATTERNS_CHARS:,}). "
        f"The output contract sits at the end of the prompt, so an oversized paste "
        f"loses the schema silently."
    )
