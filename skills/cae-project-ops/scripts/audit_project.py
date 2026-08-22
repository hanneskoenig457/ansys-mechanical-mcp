#!/usr/bin/env python3
"""Read-only structural audit for an engineering project."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
WIKILINK = re.compile(r"\[\[([^]|#]+)(?:#[^]|]+)?(?:\|[^]]+)?\]\]")
SKIP_PARTS = {".git", ".venv", "node_modules", "__pycache__"}
CLUTTER_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}
CLUTTER_SUFFIXES = (".tmp", ".swp", ".bak", ".orig")


def markdown_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.md")
        if not any(part in SKIP_PARTS for part in path.relative_to(root).parts)
    )


def resolve_markdown_link(source: Path, target: str) -> Path | None:
    clean = target.split("#", 1)[0].split("?", 1)[0]
    if not clean or "://" in clean or clean.startswith("mailto:"):
        return None
    return (source.parent / clean).resolve()


def audit(root: Path) -> dict[str, object]:
    docs = markdown_files(root)
    doc_set = {path.resolve() for path in docs}
    incoming = Counter({path.resolve(): 0 for path in docs})
    broken: list[dict[str, str]] = []
    wikilinks: list[dict[str, str]] = []

    for source in docs:
        text = source.read_text(encoding="utf-8", errors="replace")
        for raw_target in MARKDOWN_LINK.findall(text):
            resolved = resolve_markdown_link(source, raw_target.strip("<>"))
            if resolved is None:
                continue
            if resolved.suffix.lower() == ".md":
                if resolved in doc_set:
                    incoming[resolved] += 1
                elif not resolved.exists():
                    broken.append(
                        {
                            "source": str(source.relative_to(root)),
                            "target": raw_target,
                        }
                    )
        for raw_target in WIKILINK.findall(text):
            wikilinks.append(
                {"source": str(source.relative_to(root)), "target": raw_target}
            )

    duplicate_names = {
        name: count
        for name, count in Counter(path.name for path in docs).items()
        if count > 1
    }
    root_readme = (root / "README.md").resolve()
    orphans = [
        str(path.relative_to(root))
        for path in docs
        if path.resolve() != root_readme and incoming[path.resolve()] == 0
    ]

    clutter: list[str] = []
    for path in root.rglob("*"):
        if any(part in SKIP_PARTS for part in path.relative_to(root).parts):
            continue
        name = path.name
        lowered = name.lower()
        if (
            name in CLUTTER_NAMES
            or name.startswith("._")
            or lowered.endswith(CLUTTER_SUFFIXES)
            or ".lock.orphan" in lowered
            or ".lock.stale" in lowered
        ):
            clutter.append(str(path.relative_to(root)))

    git_status: list[str] | None = None
    if (root / ".git").exists():
        result = subprocess.run(
            ["git", "-c", f"safe.directory={root}", "status", "--short"],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        git_status = result.stdout.splitlines()

    return {
        "root": str(root),
        "markdown_files": len(docs),
        "root_readme": (root / "README.md").is_file(),
        "agents_instructions": (root / "AGENTS.md").is_file(),
        "duplicate_markdown_filenames": duplicate_names,
        "orphan_markdown": orphans,
        "broken_markdown_links": broken,
        "obsidian_wikilinks": wikilinks,
        "cleanup_candidates": sorted(clutter),
        "git_repository": (root / ".git").exists(),
        "git_status": git_status,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    root = args.project_root.expanduser().resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")

    report = audit(root)
    if args.as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    print(f"Project: {report['root']}")
    print(f"Markdown files: {report['markdown_files']}")
    print(f"Root README: {'yes' if report['root_readme'] else 'NO'}")
    print(f"AGENTS.md: {'yes' if report['agents_instructions'] else 'no'}")
    for key in (
        "duplicate_markdown_filenames",
        "orphan_markdown",
        "broken_markdown_links",
        "cleanup_candidates",
    ):
        value = report[key]
        print(f"{key}: {len(value)}")
        if value:
            for item in value:
                print(f"  - {item}")
    print(f"Git repository: {'yes' if report['git_repository'] else 'no'}")
    if report["git_status"]:
        print(f"Git changes: {len(report['git_status'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
