#!/usr/bin/env python3
"""Remove the official MCP's local-filesystem path checks from open_project
and save_project.

Why this patch exists
---------------------
In this deployment Mechanical always runs on the remote Windows VM, while the
MCP server runs on the Mac. Every path `open_project` and `save_project` ever
receive is therefore a Windows path (``C:\\...``) that by definition does not
exist on the Mac. Upstream validates those paths with ``Path(...).exists()``
against the *local* filesystem, so both tools always fail with a false
"not found" / "directory does not exist" before Mechanical is ever contacted.

The checks are wrong here in every case, not merely some, so they are removed
outright rather than made conditional. Mechanical itself still raises a real
error if the path is genuinely invalid.

Deliberately NOT patched: `upload_file`, `download_file`, `export_results`,
`screenshot` and the solve-log reader. Those legitimately take local Mac
paths, where an ``exists()`` check is correct.

This script is idempotent: running it twice is a no-op, and it exits non-zero
only if the file could not be brought into the expected state.
"""

from __future__ import annotations

import sys
from pathlib import Path

# (description, exact text to remove) - matched literally, whitespace included.
REMOVALS = [
    (
        "open_project local existence check",
        '    if not Path(file_path).exists():\n'
        '        return f"Project file not found: {file_path}"\n'
        '\n',
    ),
    (
        "save_project parent-directory check",
        '            # Ensure parent directory exists\n'
        '            parent = Path(file_path).parent\n'
        '            if not parent.exists():\n'
        '                return f"Directory does not exist: {parent}"\n'
        '\n',
    ),
]


def find_tools_module() -> Path:
    """Locate the installed MCP tools.py next to this repository's .venv."""
    repo_root = Path(__file__).resolve().parent.parent
    matches = sorted(repo_root.glob(".venv/lib/python*/site-packages/ansys/mechanical/mcp/tools.py"))
    if not matches:
        sys.exit(
            f"Could not find the installed MCP tools.py under {repo_root}/.venv .\n"
            "Create the environment first (see README: Recreate the Python environment)."
        )
    return matches[-1]


def main() -> int:
    tools = find_tools_module()
    original = tools.read_text(encoding="utf-8")
    patched = original

    applied, already = [], []
    for description, snippet in REMOVALS:
        if snippet in patched:
            patched = patched.replace(snippet, "", 1)
            applied.append(description)
        else:
            already.append(description)

    if applied:
        tools.write_text(patched, encoding="utf-8")

    for description in applied:
        print(f"patched: {description}")
    for description in already:
        print(f"already patched (or upstream changed): {description}")

    # Verify the end state rather than trusting the replace calls.
    verify = tools.read_text(encoding="utf-8")
    still_present = [d for d, s in REMOVALS if s in verify]
    if still_present:
        print(f"ERROR: still present after patching: {still_present}", file=sys.stderr)
        return 1

    if already and not applied:
        print(f"\nNo changes needed: {tools}")
    else:
        print(f"\nPatched: {tools}")

    if len(already) == len(REMOVALS) and not applied:
        print(
            "Note: if a package upgrade changed these code blocks, this script "
            "silently does nothing. Re-check open_project/save_project by hand "
            "after upgrading ansys-mechanical-mcp."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
