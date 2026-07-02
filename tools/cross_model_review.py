#!/usr/bin/env python3
"""Cross-model onboarding read for the Runway ownership doc.

Own-your-code produces `OWN_YOUR_CODE.md` — the engineering wiki a new maintainer
reads to take the repo over *without* first reading the source. The blind spot: it
is written and judged by one model family. A second, different model reading the
same doc COLD (doc only, no source) surfaces the loose ends the author can't see —
the onboarding equivalent of "hand it to someone who's never touched it and watch
where they get stuck."

This tool packages that read and records it. It is deliberately backend-pluggable
because the "different model" you have on hand varies by environment:

  --backend codex     shell out to the OpenAI Codex CLI (`codex`) if installed
  --backend openai    call the OpenAI API   (needs OPENAI_API_KEY)
  --backend anthropic call the Anthropic API (needs ANTHROPIC_API_KEY; use a
                      different model than the one that WROTE the doc)
  --backend harness   (default) no external model call — write the request package
                      for a second model driven by the surrounding agent/harness,
                      then read its reply back. This is the honest fallback when no
                      model CLI/key is wired in the environment: the orchestrator
                      (a different in-harness model) does the actual read.

Two-phase in harness mode:
  1. prepare  (default)  -> writes tools/out/<version>/request.md  (doc + reviewer prompt)
  2. --fold              -> reads tools/out/<version>/response.md, extracts the loose
                            ends, writes loose_ends.md + manifest.json

With a live backend (codex/openai/anthropic) both phases run in one invocation.

Stdlib only — no third-party deps, so it runs in the bare project venv.

Usage:
    python tools/cross_model_review.py --version v2.0                 # prepare (harness)
    python tools/cross_model_review.py --version v2.0 --fold          # fold the reply
    python tools/cross_model_review.py --version v2.0 --backend codex # one-shot, live model
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import date as _date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_DOC = REPO / "OWN_YOUR_CODE.md"
OUT_ROOT = REPO / "tools" / "out"

# The reviewer persona. The whole point is a COLD onboarding read: doc only, no
# source, different model. The prompt asks for the two things a maintainer needs —
# "what can I now do" and, more valuably, "where does the doc leave me stuck."
REVIEWER_PROMPT = """\
You are a senior engineer being ONBOARDED to a project called "Runway". You have
exactly ONE artifact: the ownership document below (`OWN_YOUR_CODE.md`). You do NOT
have the source code, the git history, or anyone to ask. Read it as if you must take
this repo over on Monday.

Judge it against one bar:
  Could a fresh engineer, from THIS DOC ALONE, (a) explain what Runway is and draw
  its component map, (b) defend each significant decision on maintainability/UX/cost,
  and (c) for a reported bug, name the responsible file and the SHAPE of the fix —
  understanding that the edit itself will open the named file?

Return your review in this exact structure:

## Confidence
2-3 sentences: what could you confidently do after this read, and what is the doc's
strongest quality?

## Loose ends
A numbered list. Each item is something that BLOCKS onboarding — a claim you can't
act on, a decision you couldn't defend, a term used before it's defined, a place the
doc says "fix it" without telling you where/how, an inconsistency, or a gap where you
would still have to open the source for something the doc implies it covers. For each:
  - **What's loose:** one line.
  - **Where:** the section / decision id (e.g. "§4 D3", "cockpit", "§7").
  - **Severity:** blocker | friction | polish.
  - **Fix:** the smallest concrete change to the DOC that would close it.
Be specific and adversarial. Do not pad. If something is genuinely fine, don't invent
a complaint — but a doc this size almost always has 3-8 real loose ends.

## Single biggest gap
One paragraph: if you could fix only one thing before taking over, what and why.

---
BEGIN OWN_YOUR_CODE.md
---
{doc}
---
END OWN_YOUR_CODE.md
---
"""


def _version_dir(version: str) -> Path:
    return OUT_ROOT / version


def _sha12(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _load_doc(doc_path: Path) -> str:
    if not doc_path.exists():
        sys.exit(f"doc not found: {doc_path}")
    return doc_path.read_text(encoding="utf-8")


def build_request(doc_text: str) -> str:
    return REVIEWER_PROMPT.format(doc=doc_text)


# --------------------------------------------------------------------------- #
# Live backends (best-effort; each returns the reviewer's raw markdown or raises)
# --------------------------------------------------------------------------- #
def run_codex(request: str) -> str:
    exe = shutil.which("codex")
    if not exe:
        raise RuntimeError("codex CLI not found on PATH")
    # `codex exec` runs a one-shot non-interactive prompt on most versions.
    proc = subprocess.run(
        [exe, "exec", "--full-auto", request],
        capture_output=True, text=True, timeout=900,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"codex exited {proc.returncode}: {proc.stderr[:500]}")
    return proc.stdout.strip()


def run_openai(request: str, model: str = "gpt-5") -> str:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")
    import urllib.request  # stdlib
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": request}],
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=900) as r:  # noqa: S310
        data = json.loads(r.read())
    return data["choices"][0]["message"]["content"].strip()


def run_anthropic(request: str, model: str = "claude-sonnet-5") -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    import urllib.request  # stdlib
    body = json.dumps({
        "model": model,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": request}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=900) as r:  # noqa: S310
        data = json.loads(r.read())
    return "".join(b.get("text", "") for b in data.get("content", [])).strip()


LIVE_BACKENDS = {"codex": run_codex, "openai": run_openai, "anthropic": run_anthropic}


# --------------------------------------------------------------------------- #
# Fold: response markdown -> structured loose ends
# --------------------------------------------------------------------------- #
def extract_loose_ends(response_md: str) -> list[dict]:
    """Pull the '## Loose ends' block into rough structured items.

    Best-effort parse: each numbered item becomes one record; the **Where** /
    **Severity** / **Fix** sub-bullets are captured if present. Kept lenient so a
    slightly-off reviewer format still yields usable rows.
    """
    lines = response_md.splitlines()
    start = next((i for i, ln in enumerate(lines)
                  if ln.strip().lower().startswith("## loose end")), None)
    if start is None:
        return []
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].strip().startswith("## ")), len(lines))
    block = lines[start + 1:end]

    items: list[dict] = []
    cur: dict | None = None
    for ln in block:
        s = ln.strip()
        if not s:
            continue
        # A new numbered item ("1.", "2)", etc.)
        if s[0].isdigit() and (s[1:2] in (".", ")")):
            if cur:
                items.append(cur)
            cur = {"item": s.split(".", 1)[-1].split(")", 1)[-1].strip(),
                   "where": "", "severity": "", "fix": ""}
            continue
        low = s.lstrip("-* ").lower()
        if cur is not None:
            if low.startswith("**what") or low.startswith("what's loose"):
                cur["item"] = s.split(":", 1)[-1].strip() or cur["item"]
            elif low.startswith("**where") or low.startswith("where"):
                cur["where"] = s.split(":", 1)[-1].strip()
            elif low.startswith("**sever") or low.startswith("severity"):
                cur["severity"] = s.split(":", 1)[-1].strip().strip("*")
            elif low.startswith("**fix") or low.startswith("fix"):
                cur["fix"] = s.split(":", 1)[-1].strip()
            else:
                # continuation of the item line
                if not cur["item"]:
                    cur["item"] = s
    if cur:
        items.append(cur)
    return items


def do_prepare(doc_path: Path, version: str, run_date: str) -> Path:
    doc_text = _load_doc(doc_path)
    vdir = _version_dir(version)
    vdir.mkdir(parents=True, exist_ok=True)
    request = build_request(doc_text)
    (vdir / "request.md").write_text(request, encoding="utf-8")
    manifest = {
        "version": version,
        "run_date": run_date,
        "doc": str(doc_path.relative_to(REPO)),
        "doc_sha12": _sha12(doc_text),
        "backend": "harness",
        "phase": "prepared",
    }
    (vdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return vdir


def do_fold(version: str, run_date: str, model_label: str) -> Path:
    vdir = _version_dir(version)
    resp = vdir / "response.md"
    if not resp.exists():
        sys.exit(f"no response at {resp} — run the reviewer and save its reply there first")
    response_md = resp.read_text(encoding="utf-8")
    loose = extract_loose_ends(response_md)
    (vdir / "loose_ends.md").write_text(
        f"# Cross-model onboarding read — loose ends ({version})\n\n"
        f"Reviewer model: {model_label} · run {run_date}\n\n"
        + (
            "\n".join(
                f"{i+1}. **{it['item']}**  \n"
                f"   - Where: {it['where'] or '—'}  \n"
                f"   - Severity: {it['severity'] or '—'}  \n"
                f"   - Fix: {it['fix'] or '—'}"
                for i, it in enumerate(loose)
            )
            if loose else "_No structured loose ends parsed; see response.md._"
        )
        + "\n",
        encoding="utf-8",
    )
    manifest_path = vdir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest.update({
        "version": version, "run_date": run_date, "backend_model": model_label,
        "phase": "folded", "loose_end_count": len(loose),
    })
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return vdir


def main() -> None:
    ap = argparse.ArgumentParser(description="Cross-model onboarding read of the ownership doc")
    ap.add_argument("--doc", default=str(DEFAULT_DOC))
    ap.add_argument("--version", required=True, help="run label, e.g. v2.0")
    ap.add_argument("--backend", default="harness",
                    choices=["harness", "codex", "openai", "anthropic"])
    ap.add_argument("--model", default="", help="override model id for the live backend")
    ap.add_argument("--fold", action="store_true", help="fold an existing response.md")
    ap.add_argument("--date", default=_date.today().isoformat(), help="run date (YYYY-MM-DD)")
    args = ap.parse_args()

    doc_path = Path(args.doc)
    if not doc_path.is_absolute():
        doc_path = (REPO / doc_path).resolve()
    vdir = _version_dir(args.version)

    # Live backend: one-shot read + fold.
    if args.backend in LIVE_BACKENDS and not args.fold:
        doc_text = _load_doc(doc_path)
        request = build_request(doc_text)
        vdir.mkdir(parents=True, exist_ok=True)
        (vdir / "request.md").write_text(request, encoding="utf-8")
        fn = LIVE_BACKENDS[args.backend]
        try:
            kwargs = {"model": args.model} if args.model else {}
            response = fn(request, **kwargs) if args.model else fn(request)
        except Exception as e:  # noqa: BLE001
            print(f"[{args.backend}] backend failed: {e}", file=sys.stderr)
            print("Falling back to harness mode: request package is written; run a "
                  "second model on it and save the reply to "
                  f"{vdir / 'response.md'}, then re-run with --fold.", file=sys.stderr)
            sys.exit(2)
        (vdir / "response.md").write_text(response, encoding="utf-8")
        model_label = args.model or args.backend
        do_fold(args.version, args.date, model_label)
        print(f"[{args.backend}] wrote response + folded loose ends to {vdir}")
        return

    if args.fold:
        model_label = args.model or os.environ.get("XMODEL_LABEL", "harness-agent")
        out = do_fold(args.version, args.date, model_label)
        print(f"folded loose ends -> {out / 'loose_ends.md'}")
        return

    # Default: prepare the request package for a harness-driven second model.
    out = do_prepare(doc_path, args.version, args.date)
    print(f"prepared cross-model onboarding read -> {out / 'request.md'}")
    print("No external model backend selected (harness mode).")
    print("Next: run a DIFFERENT model on request.md as the onboarding reviewer,")
    print(f"save its reply to {out / 'response.md'}, then re-run with --fold.")


if __name__ == "__main__":
    main()
