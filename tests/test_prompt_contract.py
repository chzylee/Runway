"""Pins for the prompt template: the contract between the site, the LLM and the report.

WHY THIS FILE EXISTS
While shortening the prompt, a rewrite of the portfolio section silently deleted
`{{PORTFOLIO}}`. Nothing caught it: the template still parsed, every role still
generated a prompt, the site's own TOKENS presence-check still passed (it only
checks tokens it knows about, and the token was gone from the template, not from
the list), and the output looked entirely normal. The applicant's portfolio link
simply would never have reached the model, and the report would have been built
on the resume alone while claiming to have read a portfolio.

That class of failure - an instruction disappearing without anything going red -
is the one the prompt is most exposed to, because it is edited as prose but
behaves as code. These tests pin the parts whose absence would be silent.

MATCHING RULE
Every check runs against whitespace-collapsed text. The template is hard-wrapped
prose, so a phrase that spans a line break is still one phrase. Skipping this
produced three false failures for every real one when the checks were first run
by hand.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = REPO_ROOT / "prompts" / "recommendations.md"
MIRROR = REPO_ROOT / "web" / "prompts" / "recommendations.md"
APP_JS = REPO_ROOT / "web" / "app.js"
REPORT_HTML = REPO_ROOT / "web" / "report_template.html"


def _read(path: Path) -> str:
    assert path.exists(), f"missing: {path.relative_to(REPO_ROOT)}"
    return path.read_text(encoding="utf-8")


def _flat(text: str) -> str:
    """Collapse whitespace so a hard-wrapped phrase still matches."""
    return re.sub(r"\s+", " ", text)


@pytest.fixture(scope="module")
def template() -> str:
    return _read(TEMPLATE)


@pytest.fixture(scope="module")
def flat_template(template: str) -> str:
    return _flat(template)


# --------------------------------------------------------------- fill tokens

# Every token the site fills. Dropping one is invisible at runtime: the prompt
# still generates, and the missing input is simply never given to the model.
TOKENS = [
    "{{PORTFOLIO}}",
    "{{RESUME_OR_NONE}}",
    "{{CURRENT_WORK_OR_NONE}}",
    "{{SELECTED_ROWS}}",
    "{{ROLE_PATTERNS}}",
    "{{ROLE_LABEL}}",
    "{{TEMPLATE_URL}}",
    "{{STANDOUT_PATHS}}",
]


@pytest.mark.parametrize("token", TOKENS)
def test_every_fill_token_is_present(template: str, token: str) -> None:
    """The regression that prompted this file: {{PORTFOLIO}} was deleted by a rewrite."""
    assert token in template, (
        f"{token} is missing from the template. The site will fill nothing for it, "
        f"and that input never reaches the model."
    )


def test_no_unknown_tokens_are_left_unfilled(template: str) -> None:
    """A token in the template that the site does not fill ships as literal braces."""
    found = set(re.findall(r"\{\{[A-Z_]+\}\}", template))
    # {{TOKENS}} is prose in the header explaining the convention, not a fill site.
    unexpected = found - set(TOKENS) - {"{{TOKENS}}"}
    assert not unexpected, f"template has tokens the site never fills: {sorted(unexpected)}"


def test_site_token_list_matches_the_template(template: str) -> None:
    """app.js's TOKENS presence-check must know about exactly the template's tokens.

    Drift either way is a real bug: a token in the template but not in TOKENS is
    never filled, and a token in TOKENS but not in the template makes every
    generate fail the presence check.
    """
    app = _read(APP_JS)
    block = re.search(r"const TOKENS = \[(.*?)\];", app, re.S)
    assert block, "could not find the TOKENS array in app.js"
    declared = set(re.findall(r"\{\{[A-Z_]+\}\}", block.group(1)))
    assert declared == set(TOKENS), (
        f"app.js TOKENS and this test disagree.\n"
        f"  only in app.js: {sorted(declared - set(TOKENS))}\n"
        f"  only in test:   {sorted(set(TOKENS) - declared)}"
    )


@pytest.mark.parametrize("token", TOKENS)
def test_every_token_has_a_fill_site_in_app_js(token: str) -> None:
    """Declaring a token is not the same as substituting it."""
    app = _read(APP_JS)
    assert f'.split("{token}")' in app, (
        f"{token} is never substituted in app.js - it would reach the user as "
        f"literal braces in the copied prompt."
    )


# ------------------------------------------------------------ output contract

# Every key of the report JSON. The renderer reads these names; a rename in the
# prompt alone produces a report that parses and renders blank sections.
CONTRACT_KEYS = [
    "headline", "angle", "why",
    "skills_to_demonstrate", "skill", "grounding", "relative_to_you",
    "evidence_in_your_work", "priority",
    "one_thing_to_work_on", "mode", "recommendation", "how", "how_it_signals",
    "current_work_note",
    "distinctive_edge", "trait", "evidence_scope", "evidence", "sources",
    "why_it_could_matter",
    "standout_path", "recommended", "path", "why_them", "others",
    "already_have_it", "note", "source",
    "company_notes", "company", "signal_in_filings", "researched_context",
    "what_to_know", "point", "detail",
    "run_record", "portfolio_read", "resume_read", "current_work_provided",
    "research_performed", "research_tool",
]

# Enum strings are quoted verbatim in the contract. A silently changed value
# renders as an unrecognised tag rather than failing loudly.
ENUMS = [
    "already_shown | partial | gap",
    "new_project | deepen_existing | reframe_existing",
    "target | adjacent | none",
    "exa | web_search | none",
]


@pytest.mark.parametrize("key", CONTRACT_KEYS)
def test_contract_key_present(template: str, key: str) -> None:
    assert f'"{key}"' in template, f'output contract lost the "{key}" field'


@pytest.mark.parametrize("enum", ENUMS)
def test_enum_values_unchanged(flat_template: str, enum: str) -> None:
    assert enum in flat_template, f"enum changed or removed: {enum}"


def test_contract_block_is_valid_json_shaped(template: str) -> None:
    """The contract is a JSON example; it must at least parse structurally."""
    block = re.search(r"```json\s*(\{.*?\})\s*```", template, re.S)
    assert block, "no fenced JSON block found in the output contract"
    # Strip trailing // comments WITHOUT touching the // inside a URL like
    # "https://…". Only a comment sitting after the last quote on a line counts.
    lines = []
    for line in block.group(1).splitlines():
        head, _, tail = line.partition("//")
        if tail and head.count('"') % 2 == 0 and not head.rstrip().endswith(":"):
            line = head.rstrip()
        lines.append(line)
    parsed = json.loads("\n".join(lines))
    assert set(parsed) >= {
        "headline", "skills_to_demonstrate", "one_thing_to_work_on",
        "company_notes", "what_to_know", "run_record",
    }, f"top-level contract keys look wrong: {sorted(parsed)}"


def test_renderer_reads_the_fields_the_contract_defines() -> None:
    """report_template.html must read the same names the prompt promises.

    These two files are edited independently and have no compile-time link, so a
    rename in one produces silently blank sections in the other.
    """
    html = _read(REPORT_HTML)
    for field in [
        "headline", "skills_to_demonstrate", "one_thing_to_work_on",
        "distinctive_edge", "standout_path", "company_notes", "what_to_know",
        "run_record", "evidence_in_your_work", "current_work_note",
        "evidence_scope", "already_have_it", "how",
    ]:
        assert field in html, f"the report renderer never reads '{field}'"


# --------------------------------------------------------- behaviour anchors

# Load-bearing instructions. Each is a short distinctive phrase rather than a
# whole sentence, so rewording survives but deletion does not. If one of these
# fails because you meant to change the rule, change the pin in the same commit -
# that is the point, the decision should be deliberate rather than incidental.
BEHAVIOURS = {
    "access-check stop": "ask and stop",
    "no inference from memory": "Never fill from memory",
    "tie-break vehicle/heading": "momentum is the *vehicle*",
    "headed-browser escalation": "headed) browser",
    "archived-snapshot ban": "archived or cached snapshot",
    "users need proof": "polish is not proof",
    "process is not a live product": "not a live product",
    "the how-field trap": "I should build faster",
    "standout others are not recommendations": "not a second and third recommendation",
    "omit standout when absent": "Omit the whole field when no paths were supplied",
    "never manufacture an edge": "Never manufacture one to flatter",
    "trust-or-check pattern": "Trust-or-check",
    "evidence named on both sides": "names its evidence on both sides",
    "durable output directory": "temp, cache, or scratch",
    "OS handler not headless": "xdg-open",
    "no agent-controlled browser": "agent-controlled browser",
    "script-block escaping rule": "replace every `</` with",
    "concision": "Omit needless words",
    "one direction not a menu": "not a menu",
    "no immigration legal advice": "No immigration legal advice",
}


@pytest.mark.parametrize("name,phrase", sorted(BEHAVIOURS.items()))
def test_behaviour_survives(flat_template: str, name: str, phrase: str) -> None:
    assert _flat(phrase) in flat_template, (
        f"the prompt lost its '{name}' instruction. If that was deliberate, "
        f"update BEHAVIOURS in the same commit."
    )


# ------------------------------------------------------------------- caveats

def test_caveats_block_markers_are_intact(template: str) -> None:
    """scripts/check_caveats_parity.py checks the CONTENT; this checks the frame.

    A lost or duplicated marker makes the parity gate silently unable to find the
    block it is supposed to be guarding.
    """
    assert template.count("CAVEATS:BEGIN") == 1, "expected exactly one CAVEATS:BEGIN"
    assert template.count("CAVEATS:END") == 1, "expected exactly one CAVEATS:END"
    assert template.index("CAVEATS:BEGIN") < template.index("CAVEATS:END")


# -------------------------------------------------------------------- mirror

def test_mirror_matches_the_source(template: str) -> None:
    """web/prompts/ is a build artifact of prompts/; the site serves the mirror.

    If they drift, the site hands users a different prompt from the one in the
    repo, and every other test here is checking a file nobody actually runs.
    """
    assert MIRROR.read_text(encoding="utf-8") == template, (
        "web/prompts/recommendations.md is out of sync with prompts/recommendations.md "
        "- run: python scripts/run.py --no-fetch"
    )
