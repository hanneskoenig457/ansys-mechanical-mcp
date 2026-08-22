#!/usr/bin/env python3
"""Create a minimal linked CAE documentation core without overwriting files."""

from __future__ import annotations

import argparse
from pathlib import Path

CORE_FILES = (
    "README.md",
    "AGENTS.md",
    "docs/project-state.md",
    "docs/model-and-assumptions.md",
    "docs/validation-evidence.md",
    "docs/reproduction.md",
    "docs/decisions/decision-index.md",
)

OPTIONAL_FILES = {
    "inputs": ("inputs/input-sources.md",),
    "workflow": ("workflow/workflow-index.md",),
    "deliverables": ("deliverables/deliverables-index.md",),
    "archive": ("archive/archive-index.md",),
}

OPTIONAL_LINKS = {
    "inputs": "- [Input sources](inputs/input-sources.md)",
    "workflow": "- [Workflow index](workflow/workflow-index.md)",
    "deliverables": "- [Deliverables](deliverables/deliverables-index.md)",
    "archive": "- [Archive](archive/archive-index.md)",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--name", required=True, help="Human-readable project name")
    parser.add_argument(
        "--include",
        action="append",
        choices=tuple(OPTIONAL_FILES),
        default=[],
        help="Add an optional project area; repeat as needed",
    )
    parser.add_argument("--apply", action="store_true", help="Create missing files")
    args = parser.parse_args()

    root = args.project_root.expanduser().resolve()
    template_root = Path(__file__).resolve().parent.parent / "assets" / "project-template"
    selected = list(CORE_FILES)
    for area in args.include:
        selected.extend(OPTIONAL_FILES[area])
    optional_links = "\n".join(OPTIONAL_LINKS[area] for area in args.include)

    existing: list[str] = []
    missing: list[str] = []
    for relative in selected:
        target = root / relative
        if target.exists():
            existing.append(relative)
            continue
        missing.append(relative)
        if args.apply:
            source = template_root / relative
            content = source.read_text(encoding="utf-8").replace(
                "{{PROJECT_NAME}}", args.name
            )
            content = content.replace("{{OPTIONAL_LINKS}}", optional_links)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    mode = "created" if args.apply else "would create"
    print(f"Project: {root}")
    print(f"Existing files preserved: {len(existing)}")
    print(f"Files {mode}: {len(missing)}")
    for relative in missing:
        print(f"  - {relative}")
    if missing and not args.apply:
        print("Dry run only; pass --apply to create these missing files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
