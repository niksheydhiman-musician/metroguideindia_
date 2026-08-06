#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
PUBLISHER_ID = "ca-pub-5420399473611868"
SCRIPT_BLOCK = (
    '  <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-5420399473611868" crossorigin="anonymous"></script>\n'
)
HEAD_OPEN_RE = re.compile(r"<head\b[^>]*>", re.IGNORECASE)
META_CHARSET_RE = re.compile(r"^([ \t]*)<meta\b[^>]*charset\s*=\s*[\"'][^\"']+[\"'][^>]*>\s*", re.IGNORECASE | re.MULTILINE)
TITLE_RE = re.compile(r"^([ \t]*)<title\b[^>]*>.*?</title>\s*", re.IGNORECASE | re.MULTILINE | re.DOTALL)


def iter_html_files() -> list[Path]:
    return [
        path
        for path in sorted(REPO_ROOT.rglob("*.html"))
        if ".git" not in path.parts and path.parts[-3:] != (".github", "agents", path.name)
    ]


def script_with_indent(indent: str) -> str:
    return f"{indent}<script async src=\"https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={PUBLISHER_ID}\" crossorigin=\"anonymous\"></script>\n"


def inject_script(html: str) -> str:
    if PUBLISHER_ID in html:
        return html

    anchor = META_CHARSET_RE.search(html)
    if anchor:
        insert_at = anchor.end()
        indent = anchor.group(1)
        return html[:insert_at] + script_with_indent(indent) + html[insert_at:]

    anchor = TITLE_RE.search(html)
    if anchor:
        insert_at = anchor.end()
        indent = anchor.group(1)
        return html[:insert_at] + script_with_indent(indent) + html[insert_at:]

    anchor = HEAD_OPEN_RE.search(html)
    if anchor:
        insert_at = anchor.end()
        return html[:insert_at] + "\n" + SCRIPT_BLOCK + html[insert_at:]

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
