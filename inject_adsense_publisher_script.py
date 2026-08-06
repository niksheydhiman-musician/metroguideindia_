#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
PUBLISHER_ID = "ca-pub-5420399473611868"
HEAD_OPEN_RE = re.compile(r"<head\b[^>]*>", re.IGNORECASE)
META_CHARSET_RE = re.compile(
    r"^([ \t]*)(<meta\b[^>\n]*charset\s*=\s*[\"'][^\"']+[\"'][^>\n]*>)([ \t]*)(\r?\n)?",
    re.IGNORECASE | re.MULTILINE,
)
TITLE_RE = re.compile(
    r"^([ \t]*)(<title\b[^>]*>.*?</title>)([ \t]*)(\r?\n)?",
    re.IGNORECASE | re.MULTILINE,
)


def iter_html_files() -> list[Path]:
    return [
        path
        for path in sorted(REPO_ROOT.rglob("*.html"))
        if ".git" not in path.parts and path.parts[-3:] != (".github", "agents", path.name)
    ]


def script_with_indent(indent: str) -> str:
    return f'{indent}<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={PUBLISHER_ID}" crossorigin="anonymous"></script>'


def inject_after_pattern(html: str, pattern: re.Pattern[str]) -> str | None:
    match = pattern.search(html)
    if not match:
        return None

    indent = match.group(1)
    line = match.group(2)
    trailing = match.group(3)
    newline = match.group(4) or "\n"
    inserted = f"{indent}{line}{trailing}{newline}{script_with_indent(indent)}{newline}"
    return html[:match.start()] + inserted + html[match.end():]


def inject_script(html: str) -> str:
    if PUBLISHER_ID in html:
        return html

    updated = inject_after_pattern(html, META_CHARSET_RE)
    if updated is not None:
        return updated

    updated = inject_after_pattern(html, TITLE_RE)
    if updated is not None:
        return updated

    anchor = HEAD_OPEN_RE.search(html)
    if anchor:
        insert_at = anchor.end()
        return html[:insert_at] + "\n" + script_with_indent("  ") + "\n" + html[insert_at:]

    return html


def main() -> None:
    modified_files: list[Path] = []
    skipped_existing = 0
    skipped_missing_head = 0

    for path in iter_html_files():
        html = path.read_text(encoding="utf-8")
        if PUBLISHER_ID in html:
            skipped_existing += 1
            continue

        updated = inject_script(html)
        if updated == html:
            skipped_missing_head += 1
            continue

        path.write_text(updated, encoding="utf-8")
        modified_files.append(path)

    print(f"Modified files: {len(modified_files)}")
    print(f"Skipped existing: {skipped_existing}")
    print(f"Skipped missing <head>: {skipped_missing_head}")
    for path in modified_files:
        print(path.relative_to(REPO_ROOT).as_posix())


if __name__ == "__main__":
    main()
