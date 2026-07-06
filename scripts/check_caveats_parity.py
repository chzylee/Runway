"""Build-time check: the caveats embedded in prompts/recommendations.md must be
byte-for-byte identical to the engine's single-source `_util.CAVEATS` (design doc
§7 — one source of truth for the five caveats).

The prompt template is a repo file the site fetches and interpolates (D5), so its
caveats are shown to applicants without ever passing through the engine. If the
template's caveats silently drift from the engine's, the site and the LLM prompt
would carry different disclaimers than the data artifacts do. This check makes
that drift a hard, plain-English failure instead of a silent inconsistency.

Run standalone (`python scripts/check_caveats_parity.py`) or import
`check_caveats_parity()` from run.py / the workflow. Deferred JS/behavioral tests
will also call it. It has no data dependency, so it is safe to run any time.
"""
import re

from _util import CAVEATS, run_cli

from engine import RunwayError

# Resolve the template relative to this file so the check works from any CWD.
from pathlib import Path

RECOMMENDATIONS_PATH = Path(__file__).resolve().parents[1] / "prompts" / "recommendations.md"

_BLOCK = re.compile(
    r"<!--\s*CAVEATS:BEGIN.*?-->\s*(.*?)\s*<!--\s*CAVEATS:END\s*-->",
    re.DOTALL,
)


def _extract_template_caveats(text):
    """Pull the caveat lines out of the marked block, stripping the `- ` bullet.
    A missing block is itself a failure (someone deleted the marker)."""
    match = _BLOCK.search(text)
    if match is None:
        raise RunwayError(
            f"{RECOMMENDATIONS_PATH.name}: the CAVEATS:BEGIN/END block is missing.\n"
            "The five caveats must live between those markers so the parity check\n"
            "can verify them against the engine. Restore the block."
        )
    lines = []
    for raw in match.group(1).splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if not stripped.startswith("- "):
            raise RunwayError(
                f"{RECOMMENDATIONS_PATH.name}: non-caveat line inside the CAVEATS block:\n"
                f"  {stripped!r}\n"
                "Every line between the markers must be a `- <caveat>` bullet."
            )
        lines.append(stripped[2:])
    return lines


def check_caveats_parity():
    """Raise RunwayError unless recommendations.md's caveats == engine CAVEATS,
    same strings, same order. Returns the count on success."""
    if not RECOMMENDATIONS_PATH.exists():
        raise RunwayError(
            f"{RECOMMENDATIONS_PATH} is missing — the prompt template the site "
            "fetches (design doc D5) is not in the repo."
        )
    template = _extract_template_caveats(
        RECOMMENDATIONS_PATH.read_text(encoding="utf-8")
    )
    if template != list(CAVEATS):
        # Point at the first divergence so the fix is obvious.
        detail = []
        for i in range(max(len(template), len(CAVEATS))):
            t = template[i] if i < len(template) else "<missing>"
            e = CAVEATS[i] if i < len(CAVEATS) else "<missing>"
            if t != e:
                detail.append(f"  caveat {i + 1}:\n    template: {t!r}\n    engine:   {e!r}")
        raise RunwayError(
            f"{RECOMMENDATIONS_PATH.name} caveats have drifted from engine "
            "_util.CAVEATS (design doc §7 requires one source of truth):\n"
            + "\n".join(detail)
        )
    print(f"[caveats-parity] OK - {len(template)} caveats match engine _util.CAVEATS")
    return len(template)


if __name__ == "__main__":
    run_cli(check_caveats_parity)
