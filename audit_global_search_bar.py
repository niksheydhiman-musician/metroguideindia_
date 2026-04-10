#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

SEARCH_SECTION = """
<section id=\"global-search-section\" style=\"margin:28px 0 36px\">\n  <div class=\"sec-eye\">Route Planner</div>\n  <h2 class=\"sec-head\" style=\"margin-bottom:10px\">Plan a Route</h2>\n  <p style=\"color:var(--muted);font-size:.88rem;margin:0 0 14px\">Search any two stations to open the route planner with the correct city dataset.</p>\n  <div class=\"sc\">\n    <div class=\"fd\">\n      <label class=\"fl\" for=\"global-src-search\">From</label>\n      <div class=\"ac-wrap\">\n        <input type=\"text\" id=\"global-src-search\" class=\"ac-input\" placeholder=\"Search station…\" autocomplete=\"off\" spellcheck=\"false\" aria-label=\"Source station\">\n        <input type=\"hidden\" id=\"global-src\">\n        <ul class=\"ac-list\" id=\"global-src-list\" hidden></ul>\n      </div>\n    </div>\n\n    <div class=\"swap-row\">\n      <button class=\"swap\" id=\"global-swap-btn\" title=\"Swap stations\" aria-label=\"Swap stations\" type=\"button\">\n        <svg width=\"14\" height=\"14\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2.4\"><path d=\"M7 16l-4-4 4-4M17 8l4 4-4 4M3 12h18\"/></svg>\n      </button>\n    </div>\n\n    <div class=\"fd\">\n      <label class=\"fl\" for=\"global-dst-search\">To</label>\n      <div class=\"ac-wrap\">\n        <input type=\"text\" id=\"global-dst-search\" class=\"ac-input\" placeholder=\"Search station…\" autocomplete=\"off\" spellcheck=\"false\" aria-label=\"Destination station\">\n        <input type=\"hidden\" id=\"global-dst\">\n        <ul class=\"ac-list\" id=\"global-dst-list\" hidden></ul>\n      </div>\n    </div>\n\n    <button class=\"btn-find\" id=\"global-find-btn\" type=\"button\"><span class=\"btn-label\">Find Route</span></button>\n  </div>\n</section>
""".strip()

GLOBAL_SCRIPT_TAG = '<script src="/js/globalSearchBar.js?v=20260410"></script>'


@dataclass
class AuditResult:
    html_path: Path
    had_search: bool
    injected_section: bool
    injected_script: bool


def iter_html_files(root: Path):
    for path in sorted(root.rglob("*.html")):
        if "/.git/" in str(path):
            continue
        yield path


def has_search_container(content: str) -> bool:
    if 'id="global-search-section"' in content:
        return True
    return (
        'id="src-search"' in content
        and 'id="dst-search"' in content
        and 'id="find-btn"' in content
    )


def inject_section(content: str) -> tuple[str, bool]:
    if has_search_container(content):
        return content, False
    lower = content.lower()
    if "</main>" in lower:
        idx = lower.rfind("</main>")
        return content[:idx] + "\n\n" + SEARCH_SECTION + "\n" + content[idx:], True
    if "</body>" in lower:
        idx = lower.rfind("</body>")
        return content[:idx] + "\n\n" + SEARCH_SECTION + "\n" + content[idx:], True
    return content + "\n\n" + SEARCH_SECTION + "\n", True


def inject_script(content: str) -> tuple[str, bool]:
    if '/js/globalSearchBar.js' in content:
        return content, False
    lower = content.lower()
    if "</body>" in lower:
        idx = lower.rfind("</body>")
        return content[:idx] + "\n" + GLOBAL_SCRIPT_TAG + "\n" + content[idx:], True
    return content + "\n" + GLOBAL_SCRIPT_TAG + "\n", True


def process_html(path: Path, write: bool) -> AuditResult:
    original = path.read_text(encoding="utf-8")
    had_search = has_search_container(original)

    updated, section_added = inject_section(original)
    updated, script_added = inject_script(updated)

    if write and updated != original:
        path.write_text(updated, encoding="utf-8")

    return AuditResult(
        html_path=path,
        had_search=had_search,
        injected_section=section_added,
        injected_script=script_added,
    )


def run(write: bool = True) -> int:
    results = [process_html(path, write=write) for path in iter_html_files(REPO_ROOT)]

    total = len(results)
    had_search = sum(1 for r in results if r.had_search)
    injected_sections = sum(1 for r in results if r.injected_section)
    injected_scripts = sum(1 for r in results if r.injected_script)

    print(f"[audit] HTML files scanned: {total}")
    print(f"[audit] Already had planner container: {had_search}")
    print(f"[audit] Injected planner container: {injected_sections}")
    print(f"[audit] Injected global search script tag: {injected_scripts}")

    if injected_sections:
        print("[audit] Pages updated with planner container:")
        for res in results:
            if res.injected_section:
                print(f"  - {res.html_path.relative_to(REPO_ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(run(write=True))
