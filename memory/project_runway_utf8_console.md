---
name: project_runway_utf8_console
description: Runway runs on a Japanese-locale Windows console (cp932); scripts must force UTF-8 or crash on non-ASCII
metadata:
  type: project
---

The user's Windows machine has a legacy console codepage (cp932, Japanese locale). Any Python script that prints or writes non-ASCII (em-dashes `—`, `≥`, `→`, curly quotes) crashes with `UnicodeEncodeError: 'cp932' codec can't encode...` — even though it works fine on a UTF-8 machine.

**Why:** Python inherits the console's locale encoding for stdout and `Path.write_text`/`read_text` unless told otherwise. This is invisible to the builder on a non-JP machine, so it's a recurring "works on my machine" trap for this project.

**How to apply:** Every entrypoint script in Runway starts with a `sys.stdout/stderr.reconfigure(encoding="utf-8")` guard, `run.py` sets `PYTHONUTF8=1`/`PYTHONIOENCODING=utf-8` for its subprocesses, and all file I/O passes `encoding="utf-8"`. Keep this in any new script. Relates to [[feedback_cross_platform_run_instructions]].
