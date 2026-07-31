#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
TARGET_DIRS = (
    REPO_ROOT / "routes",
    REPO_ROOT / "namo-bharat" / "stations",
)
GUIDE_SLUG = "namo-bharat-rrts-guide-2026"
BANNER_HTML = """<!-- Namo Bharat Master Guide Banner -->
<section class="mgi-guide-banner" style="margin: 3rem 0 2rem; padding: 1.5rem; background: linear-gradient(135deg, #FDF0EC 0%, #FFFFFF 100%); border: 1px solid #EDE9E3; border-left: 4px solid #C84B31; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.03);">
  <div style="display: flex; flex-direction: column; gap: 0.75rem; align-items: flex-start;">
    <div style="display: flex; align-items: center; gap: 8px;">
      <span style="font-size: 0.75rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; background: #C84B31; color: #FFFFFF; padding: 2px 8px; border-radius: 4px;">Essential Read</span>
      <span style="font-size: 0.85rem; color: #666666; font-weight: 500;">Namo Bharat RRTS Network</span>
    </div>
    <h3 style="margin: 0; font-size: 1.1rem; font-weight: 700; color: #1A1A1A; line-height: 1.4;">
      Planning a journey across the Delhi–Meerut RRTS corridor?
    </h3>
    <p style="margin: 0; font-size: 0.9rem; color: #555555; line-height: 1.5;">
      Read our detailed <a href="https://metroguideindia.com/blog/namo-bharat-rrts-guide-2026-routes-stations-timings-fare-complete-travel-guide.html" style="color: #C84B31; font-weight: 600; text-decoration: underline;" title="Complete Namo Bharat RRTS Travel Guide 2026">Complete Namo Bharat RRTS Travel Guide (2026)</a> for in-depth insights on system rules, premium vs standard coaches, card recharges, and full corridor maps.
    </p>
  </div>
</section>
<!-- End Namo Bharat Master Guide Banner -->"""


def is_target_page(path: Path, html: str) -> bool:
    if path.parent.name == "routes":
        return "Namo Bharat" in html or "RRTS" in html
    return path.parent.name == "stations" and path.parent.parent.name == "namo-bharat" and path.stem != "index"


def inject_banner(html: str) -> str:
    footer_index = html.find("<footer")
    if footer_index != -1:
        return html[:footer_index].rstrip() + "\n\n" + BANNER_HTML + "\n\n" + html[footer_index:]

    search_index = html.find('<section id="global-search-section"')
    if search_index != -1:
        return html[:search_index].rstrip() + "\n\n" + BANNER_HTML + "\n\n" + html[search_index:]

    main_close_index = html.rfind("</main>")
    if main_close_index != -1:
        return html[:main_close_index].rstrip() + "\n\n" + BANNER_HTML + "\n" + html[main_close_index:]

    raise ValueError("Could not find footer, global search section, or </main> anchor")


def iter_target_files() -> list[Path]:
    files: list[Path] = []
    for directory in TARGET_DIRS:
        files.extend(sorted(directory.glob("*.html")))
    return files


def run() -> tuple[int, int, int]:
    modified = 0
    skipped_existing = 0
    skipped_non_target = 0

    for path in iter_target_files():
        html = path.read_text(encoding="utf-8")
        if not is_target_page(path, html):
            skipped_non_target += 1
            continue
        if GUIDE_SLUG in html:
            skipped_existing += 1
            continue

        updated = inject_banner(html)
        if updated != html:
            path.write_text(updated, encoding="utf-8")
            modified += 1

    return modified, skipped_existing, skipped_non_target


if __name__ == "__main__":
    modified, skipped_existing, skipped_non_target = run()
    print(f"Modified files: {modified}")
    print(f"Skipped existing: {skipped_existing}")
    print(f"Skipped non-target: {skipped_non_target}")
